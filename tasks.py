"""
Robot Ordering Automation Script

https://robotsparebinindustries.com
This Robot automates the process of ordering robots from RobotSpareBin Industries Inc.
It downloads order data from a CSV file, processes each order, captures screenshots,
generates PDF receipts with embedded images, and creates a ZIP archive of all receipts.
"""

from robocorp.tasks import task
from robocorp import browser
from RPA.HTTP import HTTP
from RPA.PDF import PDF
from RPA.Archive import Archive
from RPA.Tables import Tables
from pathlib import Path
import time

# Declaring Constants
ROBOT_ORDER_URL = "https://robotsparebinindustries.com/#/robot-order"
ORDERS_CSV_URL = "https://robotsparebinindustries.com/orders.csv"
ORDERS_CSV_FILE = "orders.csv"

# Output directories
SCREENSHOTS_DIR = Path("output/orders_screenshots")
RECEIPTS_DIR = Path("output/receipt_pdf")
ARCHIVE_PATH = Path("output/receipts_zip.zip")

# Retry configuration
MAX_RETRIES = 10
MODAL_TIMEOUT = 1000  # milliseconds
ERROR_TIMEOUT = 2000  # milliseconds

#Initializing RPA Libraries

_pdf = None
_http = None
_tables = None
_archive = None
_page = None

def get_pdf():
    """Get or create PDF instance"""
    global _pdf
    if _pdf is None:
        _pdf = PDF()
    return _pdf


def get_http():
    """Get or create HTTP instance"""
    global _http
    if _http is None:
        _http = HTTP()
    return _http


def get_tables():
    """Get or create Tables instance"""
    global _tables
    if _tables is None:
        _tables = Tables()
    return _tables


def get_archive():
    """Get or create Archive instance"""
    global _archive
    if _archive is None:
        _archive = Archive()
    return _archive

def get_page():
    """Get or create page instance"""
    global _page
    if _page is None:
        _page = browser.page()
    return _page


@task
def order_robots_from_RobotSpareBin():
    """
    Main task function that orchestrates the entire robot ordering process.
    
    This function:
    1. Configures the browser with slow motion and visible mode (Commented code to testing)
    2. Opens the robot order website
    3. Downloads the orders CSV file
    4. Processes each order from the CSV
    5. Archives all generated receipts into a ZIP file
    
    The function handles modal dialogs that may appear during the process.
    """
    # Configure browser with slow motion (100ms delay) and visible mode for debugging
    # browser.configure(
    #     slowmo=100,
    #     headless=False 
    # )
    # Ensure output directories exist
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize page object early
    get_page()

    # Navigate to the robot order website
    open_robot_order_website()
    # Close modal that appears after opening the website
    close_annoying_modal()

    # Download and process orders
    download_csv()
    get_orders_from_csv()

    # Create ZIP archive of all generated PDF receipts
    archive_receipts()

def open_robot_order_website():
    """
    Opens the RobotSpareBin Industries robot order website.
    """
    page=get_page()
    page.goto(ROBOT_ORDER_URL)

def close_annoying_modal(timeout=MODAL_TIMEOUT):
    """
    Closes any modal dialog that appears on the page.
    """
    page = get_page()
    modal = page.locator(".modal-dialog")
    try:
        if modal.first.is_visible(timeout=timeout):
            page.click("//button[text()='OK']")
    except Exception:
        pass

def fill_and_submit_orders(order):
    """
    Fills out the robot order form and submits it for a single order.
    This function:
    1. Fills in all order form fields
    2. Previews the robot and takes a screenshot
    3. Submits the order
    4. Handles server errors with retry logic
    5. Saves the receipt as PDF
    6. Prepares for the next order
    """
    # Fill form
    page=get_page()
    page.select_option("#head",order["Head"])
    page.check(f"input[type='radio'][value='{order['Body']}']")
    page.get_by_placeholder("Enter the part number for the legs").fill(order["Legs"])
    page.get_by_placeholder("Shipping address").fill(order["Address"])

    # Preview and screenshot
    page.click("//button[text()='Preview']")
    screenshot_robot(order)

    # Submit order with retry
    submit_order_with_retry()
    
    # Save the receipt as a PDF file with embedded screenshot
    store_receipt_as_pdf(order)
    # Click "Order another" button to prepare for next order
    page.click("#order-another")
    # Close any modal that appears after ordering
    close_annoying_modal()

def download_csv():
    """
    Downloads the orders CSV file from the RobotSpareBin Industries website.
    If a file with the same name already exists, it will be overwritten.
    """
    http = HTTP()
    # Download the orders CSV file, overwriting any existing file
    http.download(url="https://robotsparebinindustries.com/orders.csv",overwrite=True)

def get_orders_from_csv():
    """
    Reads orders from the downloaded CSV file and processes each order.
    This function:
    1. Reads the orders.csv file into a table structure
    2. Iterates through each row (order) in the table
    3. Calls fill_and_submit_orders() for each order to process it
    """
    tables= Tables()
    # Read the CSV file into a table structure
    table =tables.read_table_from_csv(ORDERS_CSV_FILE)

    # Process each order in the CSV file
    for row in table:
        fill_and_submit_orders(row)

def screenshot_robot(order):
    """
    Takes a screenshot of the robot preview image.
    The screenshot is saved to the output/orders_screenshots directory with
    a filename based on the order number.
    """
    page = get_page()
    order_no = order["Order number"]
    element = page.locator("#robot-preview-image")
    screenshot_path = SCREENSHOTS_DIR / f"screenshot_{order_no}.png"
    element.screenshot(path=str(screenshot_path))

def submit_order_with_retry(max_retries=MAX_RETRIES):
    """
    Submits an order with automatic retry on server errors.
    """
    page = get_page()
    
    for attempt in range(max_retries):
        page.click("#order")
        # Wait a moment for server response
        time.sleep(0.3)
        if not has_server_error():
            if attempt > 0:
                print(f"Order succeeded after {attempt + 1} attempts")
            return True
        
        if attempt < max_retries - 1:
            print(f"Server error detected, retrying... ({attempt + 1}/{max_retries})")

    raise Exception(f"Order failed after {max_retries} retry attempts")

def has_server_error(timeout=ERROR_TIMEOUT):
    """
    Checks if a server error alert is visible on the page.
    """
    page = get_page()
    alerts = page.locator(".alert.alert-danger")
    
    try:
        return alerts.first.is_visible(timeout=timeout)
    except (TimeoutError, Exception):
        # No error present or timeout - this is fine
        return False

def store_receipt_as_pdf(order):
    """
    Converts the order receipt HTML to PDF and embeds the robot screenshot.
    This function:
    1. Extracts the receipt HTML from the page
    2. Creates a complete HTML document with the receipt and screenshot
    3. Converts the HTML to PDF format
    4. Saves the PDF to the output/receipt_pdf directory
    """
    page = get_page()
    pdf = get_pdf()
    order_no = order["Order number"]

    receipt_html = page.locator("#receipt").inner_html()
    screenshot_path = f"output/orders_screenshots/screenshot_{order_no}.png"
    pdf_path = RECEIPTS_DIR / f"receipt_{order_no}.pdf"

    # Create complete HTML document with receipt and embedded screenshot
    full_html = f"""
    <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
        </head>
        <body>
            <div>
                {receipt_html}
            </div>
            <div style=" margin:100px 400px; display:flex; justify-content:center; max-width:100%; width:200px; height:auto;"">
                <img src="{screenshot_path}" alt="Robot Preview">
            </div>
        </body>
        </html>
    """
    # Convert HTML to PDF and save to file
    pdf.html_to_pdf(full_html, str(pdf_path))


def archive_receipts():
    """
    Creates a ZIP archive containing all generated PDF receipts.
    """
    arc=get_archive()
    # Create ZIP archive of all PDF receipts
    arc.archive_folder_with_zip(str(RECEIPTS_DIR), str(ARCHIVE_PATH))

