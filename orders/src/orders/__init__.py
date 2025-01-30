from resonate.task_sources.poller import Poller
from resonate.stores.remote import RemoteStore
from resonate.resonate import Resonate
from .log_config import setup_logger
from datetime import datetime
from threading import Event
import sqlite3
import os

logger = setup_logger(__name__)

resonate = Resonate(
    store=RemoteStore(url="http://localhost:8001"),
    task_source=Poller(url="http://localhost:8002", group="orders-service-nodes"),
)


def start_orders_db():
    db_path = os.path.join(os.path.dirname(__file__), "orders.db")
    db = sqlite3.connect(db_path, check_same_thread=False)
    stmt = db.cursor()
    stmt.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_status TEXT NOT NULL,
            order_total INTEGER DEFAULT 0,
            order_delivery_fee INTEGER DEFAULT 5,
            order_items_total INTEGER DEFAULT 0,
            customer_email INTEGER NOT NULL,
            customer_name TEXT DEFAULT NULL,
            customer_delivery_address TEXT DEFAULT NULL,
            order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            payment_confirmation_promise_id TEXT DEFAULT NULL,
            restaurant_confirmation_promise_id TEXT DEFAULT NULL,
            ready_for_pickup_promise_id TEXT DEFAULT NULL,
            driver_confirmation_promise_id TEXT DEFAULT NULL,
            out_for_delivery_promise_id TEXT DEFAULT NULL,
            delivery_confirmation_promise_id TEXT DEFAULT NULL
        );
    """
    )
    stmt.execute(
        """
        CREATE TABLE IF NOT EXISTS order_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            product_display TEXT NOT NULL,
            product_price REAL NOT NULL,
            product_image TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        );
    """
    )
    db.commit()
    logger.info("order database initialized")
    return db


@resonate.register
def add_to_cart_workflow(ctx, data):
    try:
        logger.info(f"add_to_cart_workflow started for order: {data['order_id']}")
        print(data)
        add_to_cart_result = yield ctx.lfc(add_to_cart, data)
        logger.info(add_to_cart_result["message"])
        get_cart_result = yield ctx.lfc(get_or_create_cart, data["customer_email"])
        logger.info(get_cart_result["message"])
        cart = get_cart_result["cart"]
        print(cart)
        cart = yield ctx.lfc(update_cart_totals, cart)
        return {
            "success": True,
            "message": "Product added to cart successfully",
            "cart": cart,
        }
    except Exception as e:
        error_message = f"Error in Add to Cart Workflow: {str(e)}"
        logger.error(error_message)
        raise Exception(error_message)


def add_to_cart(ctx, data):
    try:
        logger.info(
            f"adding {data['product']['product_name']} to cart {data['order_id']}"
        )
        db = ctx.get_dependency("orders-db")
        stmt = db.cursor()
        stmt.execute(
            """
            INSERT INTO order_items (order_id, product_name, product_display, product_price, product_image)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                data["order_id"],
                data["product"]["product_name"],
                data["product"]["product_display"],
                data["product"]["product_price"],
                data["product"]["product_image"],
            ),
        )
        db.commit()
        return {
            "success": True,
            "message": "product added to cart successfully",
        }
    except Exception as e:
        logger.error(e)
        raise Exception(f"error adding product to cart: {str(e)}")


@resonate.register
def remove_from_cart_workflow(ctx, data):
    try:
        logger.info(f"remove_from_cart_workflow started for order: {data['order_id']}")
        remove_from_cart_result = yield ctx.lfc(remove_from_cart, data)
        logger.info(remove_from_cart_result["message"])
        get_cart_result = yield ctx.lfc(get_or_create_cart, data["customer_email"])
        logger.info(get_cart_result["message"])
        cart = get_cart_result["cart"]
        cart = yield ctx.lfc(update_cart_totals, cart)
        return {
            "success": True,
            "cart": cart,
            "message": "Product removed from cart successfully",
        }
    except Exception as e:
        logger.error(e)
        raise Exception(f"Error in Remove from Cart Workflow: {str(e)}")


@resonate.register
def update_cart_totals(ctx, cart):
    print(cart)
    try:
        cart_item_count = len(cart["items"])
        cart["cart_item_count"] = cart_item_count
        items_total = 0
        for item in cart["items"]:
            items_total += item["product_price"]
        cart["order_items_total"] = items_total
        cart["order_total"] = items_total + cart["order_delivery_fee"]
        _ = yield ctx.lfc(update_order_by_id, cart)
        return cart
    except Exception as e:
        logger.error(e)
        raise Exception(f"error updating cart totals: {str(e)}")


@resonate.register
def get_customer_orders(ctx, customer_email):
    logger.info(f"Getting order history for customer: {customer_email}")
    try:
        db = ctx.get_dependency("orders-db")

        # Set row_factory to return rows as dictionaries
        db.row_factory = sqlite3.Row
        stmt = db.cursor()

        # Fetch orders for the given customer, excluding 'cart' status
        stmt.execute(
            "SELECT * FROM orders WHERE customer_email = ? AND order_status != 'cart' ORDER BY order_date DESC",
            (customer_email,),
        )
        orders = stmt.fetchall()

        # Convert orders into dictionaries dynamically
        orders_with_items = []
        for order in orders:
            order_dict = dict(order)  # Convert SQLite Row object to a dictionary
            order_id = order["order_id"]

            # Fetch order items for the current order_id
            stmt.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
            items = stmt.fetchall()

            # Convert items into dictionaries dynamically
            order_dict["order_items"] = [dict(item) for item in items]

            # Append to the list
            orders_with_items.append(order_dict)

        return {
            "success": True,
            "message": "Order history retrieved successfully.",
            "orders": orders_with_items,
        }
    except Exception as e:
        error_message = f"Error retrieving order history for {customer_email}: {str(e)}"
        logger.error(error_message)
        raise Exception(error_message)


@resonate.register
def get_in_progress_orders(ctx):
    logger.info("getting all in-progress orders")
    try:
        # Set up row factory for named access
        db = ctx.get_dependency("orders-db")
        db.row_factory = sqlite3.Row  # Ensure rows are dictionaries
        stmt = db.cursor()

        # Query in-progress orders (exclude 'cart' and 'payment_required')
        stmt.execute(
            "SELECT * FROM orders WHERE order_status != 'cart' AND order_status != 'payment_required' AND order_status != 'delivered'"
        )
        orders = stmt.fetchall()

        # For each order, fetch the corresponding order_items
        orders_with_items = []
        for order in orders:
            try:
                stmt.execute(
                    "SELECT * FROM order_items WHERE order_id = ?", (order["order_id"],)
                )
                items = stmt.fetchall()

                # Convert rows to dictionaries and append
                orders_with_items.append(
                    {
                        **dict(order),  # Convert the order row to a dictionary
                        "order_items": [
                            dict(item) for item in items
                        ],  # Convert all items to dictionaries
                    }
                )
            except Exception as item_error:
                error_message = (
                    f"error fetching items for order {order['order_id']}: {item_error}"
                )
                logger.error(error_message)
                raise Exception(error_message)

        return {
            "success": True,
            "message": "In-progress orders retrieved successfully.",
            "orders": orders_with_items,
        }
    except Exception as e:
        error_message = f"Error during in-progress orders retrieval: {e}"
        logger.error(error_message)
        raise Exception(error_message)


@resonate.register
def get_deliverable_orders(ctx):
    logger.info(f"getting all deliverable orders")
    try:
        db = ctx.get_dependency("orders-db")  # Assuming this is your dependency getter
        db.row_factory = sqlite3.Row
        stmt = db.cursor()
        stmt.execute(
            """
            SELECT * FROM orders 
            WHERE order_status IN ('restaurant_confirmed', 'driver_confirmed', 'ready_for_pickup', 'out_for_delivery')
            """
        )
        orders = stmt.fetchall()
        orders_with_items = []
        for order_row in orders:
            order = dict(order_row)
            stmt.execute(
                "SELECT * FROM order_items WHERE order_id = ?", (order["order_id"],)
            )
            items = stmt.fetchall()
            order["items"] = [
                dict(item) for item in items
            ]  # Convert each item to a dictionary
            orders_with_items.append(order)

        return {
            "success": True,
            "orders": orders_with_items,
            "message": "Deliverable orders retrieved successfully",
        }
    except Exception as e:
        error_message = f"error fetching deliverable orders: {str(e)}"
        logger.error(error_message)
        raise Exception(error_message)


@resonate.register
def get_or_create_cart(ctx, customer_email):
    logger.info(f"getting or creating cart for customer: {customer_email}")
    try:
        db = ctx.get_dependency("orders-db")
        db.row_factory = sqlite3.Row  # Ensure rows are dictionary-like
        stmt = db.cursor()

        # Check if a cart already exists for the customer
        stmt.execute(
            "SELECT * FROM orders WHERE customer_email = ? AND order_status = 'cart'",
            (customer_email,),
        )
        cart = stmt.fetchone()

        if cart:
            logger.info(f"cart found for {customer_email}.")
            order_id = cart["order_id"]

            # Fetch associated order items
            stmt.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
            items = stmt.fetchall()

            return {
                "success": True,
                "message": "cart retrieved successfully",
                "cart": {
                    **dict(cart),  # Convert the cart row to a dictionary
                    "items": [
                        dict(item) for item in items
                    ],  # Convert items to dictionaries
                },
            }

        # If no cart is found, create a new cart
        logger.info(f"cart not found for {customer_email}, creating a new cart")
        date = datetime.now()
        stmt.execute(
            "INSERT INTO orders (order_status, customer_email, order_date) VALUES ('cart', ?, ?)",
            (customer_email, date),
        )
        db.commit()
        new_order_id = stmt.lastrowid

        return {
            "success": True,
            "message": "Cart created successfully.",
            "cart": {
                "order_id": new_order_id,
                "order_status": "cart",
                "customer_email": customer_email,
                "order_date": date.isoformat(),
                "items": [],  # Newly created cart has no items
            },
        }
    except Exception as e:
        error_message = f"error retrieving or creating cart: {str(e)}"
        logger.error(error_message)
        raise Exception(error_message)


@resonate.register
def remove_from_cart(ctx, data):
    try:
        logger.info(f"removing {data['item']['item_id']} from cart {data['order_id']}")
        db = ctx.get_dependency("orders-db")
        stmt = db.cursor()
        stmt.execute(
            "DELETE FROM order_items WHERE item_id = ?", (data["item"]["item_id"],)
        )
        db.commit()
        return {
            "success": True,
            "message": "product removed from cart successfully",
        }
    except Exception as e:
        raise Exception(f"error removing product from cart: {str(e)}")


@resonate.register
def get_order_by_id(ctx, order_id):
    try:
        logger.info(f"fetching order {order_id}")
        db = ctx.get_dependency("orders-db")
        db.row_factory = sqlite3.Row
        stmt = db.cursor()
        stmt.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        order = stmt.fetchone()

        if not order:
            return {"success": False, "message": f"order with ID {order_id} not found"}

        order_dict = dict(order)
        stmt.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        items = stmt.fetchall()
        order_dict["items"] = [dict(item) for item in items]

        return {
            "success": True,
            "message": "order retrieved successfully",
            "order": order_dict,
        }
    except Exception as e:
        error_message = f"error fetching order {order_id}: {str(e)}"
        logger.error(error_message)
        raise Exception(error_message)


@resonate.register
def update_order_by_id(ctx, order):
    logger.info(f"updating order with order_id {order.get('order_id')}")

    if "order_id" not in order:
        raise Exception("order_id is required to update an order")

    try:
        db = ctx.get_dependency("orders-db")
        stmt = db.cursor()

        # Construct the dynamic SQL query
        fields = [
            f"{key} = ?" for key in order.keys() if key != "order_id" and key != "items" and key != "cart_item_count"
        ]
        values = [
            order[key] for key in order.keys() if key != "order_id" and key != "items" and key != "cart_item_count"
        ]
        sql_query = f"UPDATE orders SET {', '.join(fields)} WHERE order_id = ?"

        # Execute the query
        stmt.execute(sql_query, values + [order["order_id"]])
        db.commit()

        logger.info(f"order with order_id {order['order_id']} updated successfully")
        return {
            "success": True,
            "message": f"Order with order_id {order['order_id']} updated successfully",
        }
    except Exception as e:
        error_message = f"error updating order: {str(e)}"
        logger.error(error_message)
        raise Exception(error_message)


resonate.set_dependency("orders-db", start_orders_db())


def main():
    logger.info("orders service application node running")
    Event().wait()


if __name__ == "__main__":
    main()
