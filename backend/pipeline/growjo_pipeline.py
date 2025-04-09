from backend.pipeline.scrape_growjo import scrape_growjo_data
from datetime import datetime
from backend.s3_utils import upload_file_to_s3

def growjo_s3_upload():
    """
    This function is a wrapper for the scrape_growjo function.
    It can be used to call the scraping process from other parts of the code.
    """
    csv_content = scrape_growjo_data()
    now = datetime.now()

    # Format the datetime to YYYY-MM-DD_HH-MM-SS
    formatted_time = now.strftime("%Y%m%d_%H%M%S")

    # Combine the formatted time with "growjo_data" to create the filename
    filename = f"{formatted_time}_growjo_data.csv"
    upload_file_to_s3(csv_content, filename, folder="growjo-data")
    print(filename)


growjo_s3_upload()