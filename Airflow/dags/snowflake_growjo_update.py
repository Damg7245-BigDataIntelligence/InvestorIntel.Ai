from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
import os
import json

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'scraper'))
from growjo_scraper import get_recent_updates

# Default arguments (good practice)
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Create DAG
dag = DAG(
    'snowflake_growjo_update',
    default_args=default_args,
    description='Pipeline to update Growjo data in Snowflake',
    schedule_interval='@daily',
    catchup=False
)

# 🧠 Task: Scrape and push data to XCom
def scrape_and_push(**context):
    data = get_recent_updates()
    context['ti'].xcom_push(key='growjo_data', value=data)
    print("✅ Scraped data pushed to XCom")
    print(data)

# 🖨️ Task: Pull and print the XCom data
def print_scraped_data(**context):
    data = context['ti'].xcom_pull(key='growjo_data', task_ids='scrape_growjo_data')
    print("📦 Scraped Growjo Data:")
    for item in data:
        print(item)

# 🧱 Tasks
scrape_task = PythonOperator(
    task_id='scrape_growjo_data',
    python_callable=scrape_and_push,
    provide_context=True,
    dag=dag,
)

print_task = PythonOperator(
    task_id='print_growjo_data',
    python_callable=print_scraped_data,
    provide_context=True,
    dag=dag,
)

# ⛓️ DAG Flow
scrape_task >> print_task