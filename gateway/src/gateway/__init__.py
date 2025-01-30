from resonate.task_sources.poller import Poller
from resonate.stores.remote import RemoteStore
from resonate import Resonate, DurablePromise
from resonate.utils import string_to_uuid
from resonate.targets import poll
from .log_config import setup_logger
from flask import Flask, request, jsonify
from flask_cors import CORS
import time
import json
import sys
import re

logger = setup_logger(__name__)

app = Flask(__name__)
CORS(app, resources={r"*": {"origins": "http://localhost:5173"}})

store: RemoteStore = RemoteStore(url="http://localhost:8001")
resonate = Resonate(
    store=store, task_source=Poller(url="http://localhost:8002", group="gateway")
)


########################
# WORKFLOWS
########################


@resonate.register
def create_customer_workflow(ctx, data):
    try:
        logger.info(
            f"create customer workflow started for customer: {data['customer_email']}"
        )
        create_customer_result = yield ctx.rfc("create_customer", data).options(
            send_to=poll("customers-service-nodes")
        )
        return create_customer_result
    except Exception as e:
        error_message = f"Error in Create Customer Workflow: {str(e)}"
        logger.error(error_message)
        raise Exception(error_message)


@resonate.register
def order_workflow(ctx, data):
    try:
        order_id = data["order_id"]
        logger.info("---------------------------------------------")
        logger.info(f"order workflow started for order: {order_id}")
        logger.info("---------------------------------------------")

        result = yield ctx.rfc("get_order_by_id", order_id).options(
            send_to=poll("orders-service-nodes")
        )
        logger.info(result["message"])
        order = result["order"]

        result = yield ctx.rfc("get_customer", order["customer_email"]).options(
            send_to=poll("customers-service-nodes")
        )
        logger.info(result["message"])
        customer = result["customer"]

        order["order_status"] = "payment_required"
        order["customer_name"] = customer["customer_name"]
        order["customer_delivery_address"] = customer["customer_delivery_address"]
        payment_confirmation_promise = yield ctx.rfi(
            DurablePromise(id=None)
        )
        order["payment_confirmation_promise_id"] = payment_confirmation_promise.id
        restaurant_confirmation_promise = yield ctx.rfi(
            DurablePromise(id=None)
        )
        order["restaurant_confirmation_promise_id"] = restaurant_confirmation_promise.id
        ready_for_pickup_promise = yield ctx.rfi(
            DurablePromise(id=None)
        )
        order["ready_for_pickup_promise_id"] = ready_for_pickup_promise.id
        driver_confirmation_promise = yield ctx.rfi(
            DurablePromise(id=None)
        )
        order["driver_confirmation_promise_id"] = driver_confirmation_promise.id
        out_for_delivery_promise = yield ctx.rfi(
            DurablePromise(id=None)
        )
        order["out_for_delivery_promise_id"] = out_for_delivery_promise.id
        delivery_confirmation_promise = yield ctx.rfi(
            DurablePromise(id=None)
        )
        order["delivery_confirmation_promise_id"] = delivery_confirmation_promise.id
        result = yield ctx.rfc("update_order_by_id", order).options(
            send_to=poll("orders-service-nodes")
        )
        logger.info(result["message"])

        logger.info(f"waiting on payment for order {order_id}")
        yield payment_confirmation_promise
        logger.info(f"Payment confirmed for order {order_id}")

        order["order_status"] = "payment_complete"

        result = yield ctx.rfc("update_order_by_id", order).options(
            send_to=poll("orders-service-nodes")
        )
        logger.info(result["message"])

        logger.info(f"waiting on restaurant confirmation for order {order_id}")
        yield restaurant_confirmation_promise
        logger.info(f"Restaurant confirmed for order {order_id}")

        order["order_status"] = "restaurant_confirmed"

        result = yield ctx.rfc("update_order_by_id", order).options(
            send_to=poll("orders-service-nodes")
        )

        logger.info(f"waiting on driver confirmation for order {order_id}")
        yield driver_confirmation_promise
        logger.info(f"driver confirmed for order {order_id}")

        order["order_status"] = "driver_confirmed"

        result = yield ctx.rfc("update_order_by_id", order).options(
            send_to=poll("orders-service-nodes")
        )

        logger.info(f"waiting for order to be ready for pickup")
        yield ready_for_pickup_promise
        logger.info(f"order ready for pickup")

        order["order_status"] = "ready_for_pickup"

        result = yield ctx.rfc("update_order_by_id", order).options(
            send_to=poll("orders-service-nodes")
        )

        logger.info(f"waiting for order to be out for delivery")
        yield out_for_delivery_promise
        logger.info(f"order out for delivery")

        order["order_status"] = "out_for_delivery"

        result = yield ctx.rfc("update_order_by_id", order).options(
            send_to=poll("orders-service-nodes")
        )

        logger.info(f"waiting for delivery confirmation")
        yield delivery_confirmation_promise
        logger.info(f"order delivered")

        order["order_status"] = "delivered"

        result = yield ctx.rfc("update_order_by_id", order).options(
            send_to=poll("orders-service-nodes")
        )

        logger.info(f"Order workflow complete for order {order_id}")
        return

    except Exception as e:
        logger.error(e)
        raise Exception(f"Error in Order Workflow: {str(e)}")


@resonate.register
def get_customer_view_workflow(ctx, customer_email):
    customer_view = {}
    try:
        get_customer_result = yield ctx.rfc('get_customer', customer_email).options(
            send_to=poll('customers-service-nodes')
        )
        if get_customer_result['success']:
            logger.info(get_customer_result['message'])
            customer_view['customer'] = get_customer_result['customer']
            get_cart_promise = yield ctx.rfi(
                'get_or_create_cart', customer_email
            ).options(send_to=poll('orders-service-nodes'))
            get_orders_promise = yield ctx.rfi(
                'get_customer_orders', customer_email
            ).options(send_to=poll('orders-service-nodes'))
            get_products_promise = yield ctx.rfi('get_products').options(
                send_to=poll('products-service-nodes')
            )
            get_cart_result = yield get_cart_promise
            logger.info(get_cart_result['message'])
            customer_view['cart'] = get_cart_result['cart']
            get_orders_result = yield get_orders_promise
            logger.info(get_orders_result['message'])
            customer_view['orders'] = get_orders_result['orders']
            get_products_result = yield get_products_promise
            logger.info(get_products_result['message'])
            customer_view['products'] = get_products_result['products']
            return {
                'success': True,
                'customer_view': customer_view,
                'message': "customer view retrieved successfully",
            }
        else:
            return get_customer_result
    except Exception as e:
        logger.error(e)


@resonate.register
def get_restaurant_view_workflow(ctx):
    restaurant_view = {}
    try:
        logger.info("getting restaurant view")
        get_in_progress_orders_promise = yield ctx.rfi(
            "get_in_progress_orders"
        ).options(send_to=poll("orders-service-nodes"))
        get_restaurant_customers_promise = yield ctx.rfi("get_customers").options(
            send_to=poll("customers-service-nodes")
        )
        get_restaurant_products_promise = yield ctx.rfi("get_products").options(
            send_to=poll("products-service-nodes")
        )
        in_progress_orders_result = yield get_in_progress_orders_promise
        logger.info(in_progress_orders_result["message"])
        restaurant_view["in_progress_orders"] = in_progress_orders_result["orders"]
        get_restaurant_customers_result = yield get_restaurant_customers_promise
        logger.info(get_restaurant_customers_result["message"])
        restaurant_view["customers"] = get_restaurant_customers_result["customers"]
        get_restaurant_products_result = yield get_restaurant_products_promise
        logger.info(get_restaurant_products_result["message"])
        restaurant_view["products"] = get_restaurant_products_result["products"]
        return {
            "success": True,
            "restaurant_view": restaurant_view,
            "message": "restaurant view retrieved successfully",
        }
    except Exception as e:
        error_message = f"error in Get Restaurant View Workflow: {str(e)}"
        logger.error(error_message)
        raise Exception(error_message)


@resonate.register
def get_driver_view_workflow(ctx):
    driver_view = {}
    try:
        logger.info("getting driver view")
        result = yield ctx.rfc("get_deliverable_orders").options(
            send_to=poll("orders-service-nodes")
        )
        driver_view["deliveries"] = result["orders"]
        return {
            "success": True,
            "driver_view": driver_view,
            "message": "driver view retrieved successfully",
        }
    except Exception as e:
        logger.error(e)
        raise Exception(f"error in Get Driver View Workflow: {str(e)}")


########################
# DISPATCHERS
########################


@resonate.register
def dispatch_add_product(ctx, data):
    success = yield ctx.rfc("add_product", data).options(
        send_to=poll("products-service-nodes")
    )
    return success


@resonate.register
def dispatch_remove_product(ctx, product_name):
    success = yield ctx.rfc("remove_product", product_name).options(
        send_to=poll("products-service-nodes")
    )
    return success


@resonate.register
def dispatch_get_customer_cart(ctx, customer_email):
    result = yield ctx.rfc("get_or_create_cart", customer_email).options(
        send_to=poll("orders-service-nodes")
    )
    return result


@resonate.register
def dispatch_get_in_progress_orders(ctx):
    result = yield ctx.rfc("get_in_progress_orders").options(
        send_to=poll("orders-service-nodes")
    )
    return result


########################
# CUSTOMER ENDPOINTS
########################


@app.route("/customer/create", methods=["POST"])
def create_customer_route_handler():
    logger.info("create customer route handler called")
    try:
        data = request.get_json()
        if "customer_email" not in data:
            return jsonify({"error": "'customer_email' required"}), 400
        timestamp = int(time.time())
        promise_id = f"create-customer-{data["customer_email"]}-{timestamp}"
        handle = create_customer_workflow.run(promise_id, data)
        return jsonify(handle.result()), 200
    except Exception as e:
        logger.error(e)
        return jsonify({"error": str(e)}), 500


########################
# PRODUCT ENDPOINTS
########################


@app.route("/products/add", methods=["POST"])
def add_product_route_handler():
    logger.info("Add product route handler called")
    try:
        data = request.get_json()
        timestamp = int(time.time())
        handle = dispatch_add_product.run(f"add-product-{timestamp}", data)
        return jsonify(handle.result()), 200
    except Exception as e:
        logger.error(e)
        return jsonify({"error": str(e)}), 500


@app.route("/products/remove", methods=["POST"])
def remove_product_route_handler():
    logger.info("Remove product route handler called")
    try:
        data = request.get_json()
        if "product_name" not in data:
            return jsonify({"error": "product_name required"}), 400
        product_name = data["product_name"]
        timestamp = int(time.time())
        handle = dispatch_remove_product.run(
            f"remove-product-{timestamp}", product_name
        )
        return jsonify(handle.result()), 200
    except Exception as e:
        logger.error(e)
        return jsonify({"error": str(e)}), 500


########################
# CART ENDPOINTS
########################


@app.route("/cart/get", methods=["POST"])
def get_cart_route_handler():
    logger.info("Get cart route handler called")
    try:
        data = request.get_json()
        if "customer_email" not in data:
            return jsonify({"error": "customer_email required"}), 400
        timestamp = int(time.time())
        promise_id = f"get-customer-cart-{data['customer_email']}-{timestamp}"
        handle = dispatch_get_customer_cart.run(promise_id, data["customer_email"])
        return jsonify(handle.result()), 200
    except Exception as e:
        logger.error(e)
        return jsonify({"error": str(e)}), 500


@app.route("/cart/add", methods=["POST"])
def add_to_cart_route_handler():
    logger.info("Add to cart route handler called")
    try:
        data = request.get_json()
        if (
            "customer_email" not in data
            and "product_name" not in data
            and "order_id" not in data
        ):
            return (
                jsonify(
                    {
                        "error": "'customer_email', 'product_name', and 'order_id' required"
                    }
                ),
                400,
            )
        timestamp = int(time.time())
        data["timestamp"] = timestamp
        promise_id = f"add-to-cart-{data['customer_email']}-{timestamp}"
        handle = dispatch_add_to_cart.run(promise_id, data)
        return jsonify(handle.result()), 200
    except Exception as e:
        error_message = f"error in add_to_cart_route_handler(): {str(e)}"
        logger.error(error_message)
        return jsonify({"error": error_message}), 500


@resonate.register
def dispatch_add_to_cart(ctx, data):
    try:
        result = yield ctx.rfc("add_to_cart_workflow", data).options(
            send_to=poll("orders-service-nodes")
        )
        return result
    except Exception as e:
        logger.error(e)
        raise Exception(f"error in dispatch_add_to_cart: {str(e)}")


@app.route("/cart/remove", methods=["POST"])
def remove_from_cart_route_handler():
    logger.info("Remove from cart route handler called")
    try:
        data = request.get_json()
        if "customer_email" not in data:
            return jsonify({"error": "'customer_email' required"}), 400
        timestamp = int(time.time())
        data["timestamp"] = timestamp
        promise_id = f"remove-from-cart-{data['customer_email']}-{timestamp}"
        handle = dispatch_remove_from_cart.run(promise_id, data)
        return jsonify(handle.result()), 200
    except Exception as e:
        error_message = f"error in remove_from_cart_route_handler(): {str(e)}"
        logger.error(error_message)
        return jsonify({"error": error_message}), 500


@resonate.register
def dispatch_remove_from_cart(ctx, data):
    try:
        result = yield ctx.rfc("remove_from_cart_workflow", data).options(
            send_to=poll("orders-service-nodes")
        )
        return result
    except Exception as e:
        logger.error(e)
        raise Exception(f"error in dispatch_remove_from_cart: {str(e)}")


########################
# ORDER ENDPOINTS
########################


@app.route("/order/start", methods=["POST"])
def checkout_route_handler():
    logger.info("start order route handler called")
    try:
        data = request.get_json()
        print(data)
        if "customer_email" not in data or "order_id" not in data:
            error_message = "missing 'customer_email' or 'order_id' in request data"
            logger.error(error_message)
            return jsonify({"error": error_message}), 400

        customer_email = data["customer_email"]
        order_id = data["order_id"]

        _ = order_workflow.run(
            f"start-order-workflow-{customer_email}-order-{order_id}", data
        )
        return (
            jsonify(
                {
                    "message": "order workflow started",
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(e)
        return jsonify({"error": str(e)}), 500


@app.route("/order/resolve-promise", methods=["POST"])
def resolve_promise_route_handler():
    logger.info("Payment route handler called.")
    global store
    try:
        data = request.get_json()
        print(data)
        if "promise_id" not in data:
            return jsonify({"error": "promise_id required"}), 400

        promise_id = data["promise_id"]
        logger.info(f"Resolving promise with ID: {promise_id}")
        store.promises.resolve(
            id=promise_id,
            ikey=None,
            strict=False,
            headers=None,
            data=None,
        )
        return jsonify("Promise resolved."), 200
    except Exception as e:
        logger.error(e)
        return jsonify({"error": str(e)}), 500


@app.route("/orders/get-in-progress-orders", methods=["GET"])
def get_orders_in_progress_route_handler():
    logger.info("Get in progress orders route handler called")
    try:
        timestamp = int(time.time())
        handle = dispatch_get_in_progress_orders.run(
            f"get-in-progress-orders-{timestamp}"
        )
        return jsonify(handle.result()), 200
    except Exception as e:
        logger.error(e)
        return jsonify({"error": str(e)}), 500


########################
# VIEW ENDPOINTS
########################


@app.route("/views/customer", methods=["POST"])
def customer_view_handler():
    try:
        logger.info("Get customer view route handler called")
        data = request.get_json()
        if "customer_email" not in data:
            error_message = "Missing 'customer_email' in request data"
            logger.error(error_message)
            return jsonify({"error": error_message}), 400
        customer_email = data["customer_email"]
        timestamp = int(time.time())
        promise_id = f"get-customer-view-{customer_email}-{timestamp}"
        handle = get_customer_view_workflow.run(promise_id, customer_email)
        print(handle.result())
        return jsonify(handle.result()), 200
    except Exception as e:
        logger.error(e)
        return jsonify({"error": str(e)}), 500


@app.route("/views/restaurant", methods=["GET"])
def restaurant_view_handler():
    try:
        logger.info("get restaurant view route handler called")
        timestamp = int(time.time())
        handle = get_restaurant_view_workflow.run(f"get-restaurant-view-{timestamp}")
        return jsonify(handle.result()), 200
    except Exception as e:
        logger.error(e)
        return jsonify({"error": str(e)}), 500


@app.route("/views/driver", methods=["POST"])
def driver_view_handler():
    try:
        timestamp = int(time.time())
        handle = get_driver_view_workflow.run(f"get-driver-view-{timestamp}")
        return jsonify(handle.result()), 200
    except Exception as e:
        logger.error(e)
        return jsonify({"error": str(e)}), 500


# Define a main function to start the Flask app
def main():
    logger.info("API Gateway service running on port 5000")
    app.run(host="127.0.0.1", port=5000)


# Run the main function when the script is executed
if __name__ == "__main__":
    main()
