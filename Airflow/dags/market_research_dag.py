"""
Industry Reports Data Pipeline DAG

This DAG automates the end-to-end ingestion and processing of industry reports:
1. Scrapes reports from websites or directly downloads PDFs
2. Summarizes reports using Google Gemini
3. Stores PDFs in S3
4. Stores summaries in Snowflake
5. Stores embeddings in Pinecone
"""

from datetime import datetime, timedelta
import os
import sys
import requests
from typing import List, Dict, Any

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
from airflow.exceptions import AirflowSkipException

# Add parent directory to path to ensure imports work correctly
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Now import your custom modules
from industry_research.reports_scrape import (
    DIRECT_PDFS, 
    PRINT_URLS, 
    get_report_summary_with_gemini
)
from industry_research.s3_utils import upload_pdf_to_s3
from industry_research.snowflake_utils import initialize_snowflake_objects, store_report_summary
from industry_research.vector_storage_service import generate_embeddings, store_in_pinecone
from industry_research.chunking_strategies import markdown_header_chunks

# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=3),  # Set a reasonable timeout for the entire pipeline
}

# Create the DAG
dag = DAG(
    'industry_reports_pipeline',
    default_args=default_args,
    description='Pipeline to scrape, summarize, and store industry reports',
    schedule_interval='0 0 * * 1',  # Run weekly on Mondays at midnight
    start_date=datetime(2025, 4, 1),
    catchup=False,
    tags=['reports', 'market_research'],
    max_active_runs=1,  # Only one run at a time to avoid resource contention
)

def init_snowflake():
    """Initialize Snowflake database, schema, and tables"""
    try:
        initialize_snowflake_objects()
        return "Snowflake initialization successful"
    except Exception as e:
        raise Exception(f"Snowflake initialization failed: {str(e)}")

def process_direct_pdfs() -> List[Dict[str, Any]]:
    """Download PDFs directly from URLs and process them"""
    pdf_results = []
    
    for name, url in DIRECT_PDFS.items():
        try:
            industry = name.split('_')[0]
            print(f"Downloading direct PDF: {name} from {url}")
            
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
            if response.status_code == 200:
                pdf_content = response.content
                
                # Store PDF info to be processed later
                pdf_results.append({
                    'name': name,
                    'industry': industry,
                    'content': pdf_content
                })
                print(f"Successfully downloaded {name}")
            else:
                print(f"Failed to download {name}, status code: {response.status_code}")
        
        except Exception as e:
            print(f"Error downloading {name}: {e}")
    
    if not pdf_results:
        raise AirflowSkipException("No direct PDFs were successfully downloaded")
    
    # Return results for the next task
    return pdf_results

def process_html_reports() -> List[Dict[str, Any]]:
    """Scrape reports from HTML pages using Playwright"""
    from playwright.sync_api import sync_playwright
    
    html_results = []
    
    for filename, urls in PRINT_URLS.items():
        industry = filename.split('_')[0]
        
        for i, url in enumerate(urls):
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
                    )
                    
                    print(f"Visiting: {url}")
                    page.goto(url, timeout=120000, wait_until="networkidle")
                    page.wait_for_timeout(5000)  # Wait longer for JS to load
                    
                    # Set PDF options for better quality
                    pdf_options = {
                        "format": "A4",
                        "printBackground": True,
                        "margin": {"top": "0.4in", "right": "0.4in", "bottom": "0.4in", "left": "0.4in"},
                    }
                    
                    # Generate PDF content
                    pdf_content = page.pdf(pdf_options)
                    browser.close()
                    
                    pdf_name = f"{filename}_{i+1}"
                    
                    # Store PDF info to be processed later
                    html_results.append({
                        'name': pdf_name,
                        'industry': industry,
                        'content': pdf_content
                    })
                    print(f"Successfully scraped {pdf_name}")
            
            except Exception as e:
                print(f"Error scraping {url}: {str(e)}")
    
    if not html_results:
        raise AirflowSkipException("No HTML reports were successfully scraped")
    
    # Return results for the next task
    return html_results

def generate_summaries(**context):
    """Generate summaries for all collected reports using Gemini"""
    # Get results from previous tasks
    ti = context['ti']
    direct_pdf_results = ti.xcom_pull(task_ids='process_direct_pdfs')
    html_report_results = ti.xcom_pull(task_ids='process_html_reports')
    
    # Combine all reports
    all_reports = []
    if direct_pdf_results:
        all_reports.extend(direct_pdf_results)
    if html_report_results:
        all_reports.extend(html_report_results)
    
    if not all_reports:
        raise AirflowSkipException("No reports available to summarize")
    
    # Process each report
    processed_reports = []
    for report in all_reports:
        try:
            name = report['name']
            industry = report['industry']
            pdf_content = report['content']
            
            # Generate summary using Gemini
            print(f"Generating summary for {name}")
            summary = get_report_summary_with_gemini(pdf_content, name)
            
            if summary:
                processed_reports.append({
                    'name': name,
                    'industry': industry,
                    'content': pdf_content,
                    'summary': summary
                })
                print(f"Successfully generated summary for {name}")
            else:
                print(f"Failed to generate summary for {name}")
        
        except Exception as e:
            print(f"Error generating summary for {report['name']}: {e}")
    
    if not processed_reports:
        raise AirflowSkipException("No summaries were successfully generated")
    
    return processed_reports

def store_in_s3(**context):
    """Upload PDFs to S3"""
    ti = context['ti']
    processed_reports = ti.xcom_pull(task_ids='generate_summaries')
    
    if not processed_reports:
        raise AirflowSkipException("No processed reports to store in S3")
    
    s3_results = []
    for report in processed_reports:
        try:
            name = report['name']
            industry = report['industry']
            pdf_content = report['content']
            
            # Upload PDF to S3
            presigned_url = upload_pdf_to_s3(
                file_content=pdf_content,
                filename=f"{name}.pdf",
                industry=industry
            )
            
            if presigned_url:
                s3_results.append({
                    'name': name,
                    'industry': industry,
                    'summary': report['summary'],
                    's3_url': presigned_url
                })
                print(f"Successfully uploaded {name} to S3")
            else:
                print(f"Failed to upload {name} to S3")
        
        except Exception as e:
            print(f"Error uploading {report['name']} to S3: {e}")
    
    if not s3_results:
        raise AirflowSkipException("No reports were successfully stored in S3")
    
    return s3_results

def store_in_snowflake(**context):
    """Store report summaries in Snowflake"""
    ti = context['ti']
    s3_results = ti.xcom_pull(task_ids='store_in_s3')
    
    if not s3_results:
        raise AirflowSkipException("No S3 results to store in Snowflake")
    
    snowflake_results = []
    for report in s3_results:
        try:
            name = report['name']
            industry = report['industry']
            summary = report['summary']
            
            # Store in Snowflake
            store_report_summary(
                report_id=name,
                industry=industry,
                summary=summary
            )
            
            snowflake_results.append({
                'name': name,
                'industry': industry,
                's3_url': report['s3_url'],
                'summary': summary  # Pass summary to the next task
            })
            print(f"Successfully stored {name} summary in Snowflake")
        
        except Exception as e:
            print(f"Error storing {report['name']} in Snowflake: {e}")
    
    if not snowflake_results:
        raise AirflowSkipException("No summaries were successfully stored in Snowflake")
    
    return snowflake_results

def store_in_pinecone(**context):
    """Generate embeddings and store in Pinecone"""
    ti = context['ti']
    snowflake_results = ti.xcom_pull(task_ids='store_in_snowflake')
    
    if not snowflake_results:
        raise AirflowSkipException("No Snowflake results to process for Pinecone")
    
    success_count = 0
    for report in snowflake_results:
        try:
            name = report['name']
            industry = report['industry']
            summary = report['summary']
            
            # Generate chunks for embeddings
            chunks = markdown_header_chunks(summary)
            
            if not chunks:
                print(f"No chunks generated for {name}, skipping")
                continue
                
            # Process each chunk
            embeddings_data = []
            for chunk in chunks:
                embedding = generate_embeddings(chunk)
                
                if embedding:
                    embeddings_data.append({
                        'content': chunk,
                        'embedding': embedding,
                        'metadata': {
                            'industry': industry,
                            'year': '2024',
                            'document_id': name
                        }
                    })
            
            if not embeddings_data:
                print(f"No embeddings generated for {name}, skipping")
                continue
                
            # Store embeddings in Pinecone
            store_success = store_in_pinecone(embeddings_data, index_name="deloitte-reports")
            
            if store_success:
                success_count += 1
                print(f"Successfully stored {name} embeddings in Pinecone")
            else:
                print(f"Failed to store {name} embeddings in Pinecone")
        
        except Exception as e:
            print(f"Error storing {report['name']} embeddings in Pinecone: {e}")
    
    if success_count == 0:
        raise AirflowSkipException("No embeddings were successfully stored in Pinecone")
    
    return f"Successfully stored {success_count} report embeddings in Pinecone"

# Define the tasks
init_snowflake_task = PythonOperator(
    task_id='initialize_snowflake',
    python_callable=init_snowflake,
    dag=dag,
)

# Create a task group for source extraction
with TaskGroup(group_id='extract_reports', dag=dag) as extract_reports:
    process_direct_pdfs_task = PythonOperator(
        task_id='process_direct_pdfs',
        python_callable=process_direct_pdfs,
        dag=dag,
    )
    
    process_html_reports_task = PythonOperator(
        task_id='process_html_reports',
        python_callable=process_html_reports,
        dag=dag,
    )
    
    # These tasks run in parallel within the task group
    [process_direct_pdfs_task, process_html_reports_task]

# Define the remaining tasks in the pipeline
generate_summaries_task = PythonOperator(
    task_id='generate_summaries',
    python_callable=generate_summaries,
    provide_context=True,
    dag=dag,
)

store_in_s3_task = PythonOperator(
    task_id='store_in_s3',
    python_callable=store_in_s3,
    provide_context=True,
    dag=dag,
)

store_in_snowflake_task = PythonOperator(
    task_id='store_in_snowflake',
    python_callable=store_in_snowflake,
    provide_context=True,
    dag=dag,
)

store_in_pinecone_task = PythonOperator(
    task_id='store_in_pinecone',
    python_callable=store_in_pinecone,
    provide_context=True,
    dag=dag,
)

# Define the task dependencies
extract_reports >> generate_summaries_task >> store_in_s3_task
init_snowflake_task >> store_in_snowflake_task  # Initialize Snowflake just before we need it
store_in_s3_task >> store_in_snowflake_task >> store_in_pinecone_task