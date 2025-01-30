from resonate.task_sources.poller import Poller
from resonate.stores.remote import RemoteStore
from resonate.resonate import Resonate
from .log_config import setup_logger
from threading import Event
import sqlite3
import os

logger = setup_logger(__name__)

store = RemoteStore(url="http://localhost:8001")
resonate = Resonate(
    store=store,
    task_source=Poller(url="http://localhost:8002", group="customers-service-nodes"),
)


def start_customer_db():
    db_path = os.path.join(os.path.dirname(__file__), "customers.db")
    db = sqlite3.connect(db_path, check_same_thread=False)
    stmt = db.cursor()
    stmt.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_email TEXT NOT NULL UNIQUE,
            customer_name TEXT NOT NULL,
            customer_delivery_address TEXT NOT NULL
        );
    """
    )
    db.commit()
    logger.info("customers database initialized")
    return db


@resonate.register
def get_customer(ctx, customer_email):
    try:
        logger.info(f"getting customer with email {customer_email}")
        db = ctx.get_dependency("customer-db")
        stmt = db.cursor()
        stmt.execute(
            "SELECT * FROM customers WHERE customer_email = ?", (customer_email,)
        )
        columns = [column[0] for column in stmt.description]
        customers = [dict(zip(columns, row)) for row in stmt.fetchall()]
        print(customers)
        if not customers:
            return {"success": False, "message": "Customer not found"}
        return {"success": True, "customer": customers[0], "message": "Customer found"}
    except Exception as e:
        print(f"Error retrieving customer: {str(e)}")
        raise Exception(f"Error retrieving customer: {str(e)}")


@resonate.register
def create_customer(ctx, data):
   
    try:
        logger.info("creating customer with email {data['customer_email']}")
        db = ctx.get_dependency("customer-db")
        stmt = db.cursor()

        stmt.execute(
            """
            INSERT INTO customers (customer_email, customer_name, customer_delivery_address)
            VALUES (?, ?, ?)
            """,
            (
                data["customer_email"],
                data["customer_name"],
                data["customer_delivery_address"],
            ),
        )
        db.commit()

        return {
            "success": True,
            "message": "Customer created successfully.",
        }

    except sqlite3.IntegrityError:
        error_message = f"Customer with email {data['customer_email']} already exists."
        logger.error(error_message)
        return {"success": False, "message": error_message}
    except Exception as e:
        raise Exception(f"Error inserting into customers: {str(e)}")


@resonate.register
def get_customers(ctx):
    db = ctx.get_dependency("customer-db")
    try:
        stmt = db.cursor()
        stmt.execute("SELECT * FROM customers")
        columns = [column[0] for column in stmt.description]
        # Fetch all rows and map them to dictionaries
        customers = [dict(zip(columns, row)) for row in stmt.fetchall()]
        if not customers:
            print("no rows")
        return {
            "success": True,
            "message": "customers retrieved successfully",
            "customers": customers,
        }
    except Exception as e:
        print(f"Error retrieving customer: {str(e)}")
        raise Exception(f"Error retrieving customer: {str(e)}")


resonate.set_dependency("customer-db", start_customer_db())


# Define a main function to start the Application Node
def main():
    logger.info("customers service app node running")
    Event().wait()


# Run the main function when the script is executed
if __name__ == "__main__":
    main()
