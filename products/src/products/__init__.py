from resonate.task_sources.poller import Poller
from resonate.stores.remote import RemoteStore
from resonate.resonate import Resonate
from .log_config import setup_logger
from threading import Event
import sqlite3
import os

logger = setup_logger(__name__)

resonate = Resonate(
    store=RemoteStore(url="http://localhost:8001"),
    task_source=Poller(url="http://localhost:8002", group="products-service-nodes"),
)


def start_products_db():
    db_path = os.path.join(os.path.dirname(__file__), "products.db")
    db = sqlite3.connect(db_path, check_same_thread=False)
    stmt = db.cursor()
    stmt.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL UNIQUE,
            product_display TEXT NOT NULL,
            product_price INT NOT NULL,
            product_image TEXT NOT NULL
        );
    """
    )
    db.commit()
    logger.info("products database initialized")
    return db


@resonate.register
def add_product(ctx, data):
    try:
        db = ctx.get_dependency("products-db")
        stmt = db.cursor()
        stmt.execute(
            """
            INSERT INTO products (product_name, product_display, product_price, product_image)
            VALUES (?, ?, ?, ?)
        """,
            (
                data["product_name"],
                data["product_display"],
                data["product_price"],
                data["product_image"],
            ),
        )
        db.commit()
        print("Product added to database.")
    except Exception as e:
        print("Error adding product to database:", e)
        raise Exception(f"Error adding product: {str(e)}")


@resonate.register
def get_products(ctx):
    print("Getting products from database...")
    try:
        db = ctx.get_dependency("products-db")
        stmt = db.cursor()
        stmt.execute("SELECT * FROM products")
        # Get the column names from the cursor
        columns = [column[0] for column in stmt.description]

        # Fetch all rows and map them to dictionaries
        products = [dict(zip(columns, row)) for row in stmt.fetchall()]

        return {
            "success": True,
            "message": "products retrieved successfully",
            "products": products,
        }
    except Exception as e:
        print("Error getting products from database:", e)
        raise Exception(f"Error getting products: {str(e)}")


@resonate.register
def remove_product(ctx, product_name):
    try:
        db = ctx.get_dependency("products-db")
        stmt = db.cursor()
        stmt.execute("DELETE FROM products WHERE product_name=?", (product_name,))
        db.commit()
        print("Product removed from database.")
    except Exception as e:
        print("Error removing product from database:", e)
        raise Exception(f"Error removing product: {str(e)}")


resonate.set_dependency("products-db", start_products_db())


def main():
    logger.info("products service app node running")
    Event().wait()


# Run the main function when the script is executed
if __name__ == "__main__":
    main()
