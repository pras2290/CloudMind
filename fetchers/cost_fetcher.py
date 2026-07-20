import boto3
import os
from datetime import datetime, timedelta
from langchain_core.documents import Document
from dotenv import load_dotenv

load_dotenv()

def get_boto3_client(service):
    return boto3.client(
        service,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION")
    )

def fetch_monthly_cost_by_service():
    """Fetch last 6 months cost grouped by service."""
    client = get_boto3_client("ce")

    end = datetime.today().replace(day=1).strftime("%Y-%m-%d")
    start = (datetime.today().replace(day=1) - timedelta(days=180)).strftime("%Y-%m-%d")

    response = client.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}]
    )

    docs = []
    for result in response["ResultsByTime"]:
        period = result["TimePeriod"]["Start"]
        for group in result["Groups"]:
            service = group["Keys"][0]
            cost = round(float(group["Metrics"]["UnblendedCost"]["Amount"]), 4)
            if cost > 0:
                text = f"AWS Service: {service}\nMonth: {period}\nCost: ${cost} USD"
                docs.append(Document(
                    page_content=text,
                    metadata={
                        "source": "aws_cost_explorer",
                        "service": service,
                        "month": period,
                        "type": "cost"
                    }
                ))
    return docs


def fetch_total_monthly_cost():
    """Fetch total AWS cost per month for last 6 months."""
    client = get_boto3_client("ce")

    end = datetime.today().replace(day=1).strftime("%Y-%m-%d")
    start = (datetime.today().replace(day=1) - timedelta(days=180)).strftime("%Y-%m-%d")

    response = client.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"]
    )

    docs = []
    for result in response["ResultsByTime"]:
        period = result["TimePeriod"]["Start"]
        cost = round(float(result["Total"]["UnblendedCost"]["Amount"]), 4)
        text = f"Total AWS cost for {period}: ${cost} USD"
        docs.append(Document(
            page_content=text,
            metadata={
                "source": "aws_cost_explorer",
                "month": period,
                "type": "total_cost"
            }
        ))
    return docs


def fetch_cost_forecast():
    """Fetch next month cost forecast."""
    client = get_boto3_client("ce")

    start = datetime.today().strftime("%Y-%m-%d")
    end = (datetime.today().replace(day=1) + timedelta(days=32)).replace(day=1).strftime("%Y-%m-%d")

    try:
        response = client.get_cost_forecast(
            TimePeriod={"Start": start, "End": end},
            Metric="UNBLENDED_COST",
            Granularity="MONTHLY"
        )
        forecast = round(float(response["Total"]["Amount"]), 4)
        text = f"AWS cost forecast for next month: ${forecast} USD"
        return [Document(
            page_content=text,
            metadata={"source": "aws_cost_explorer", "type": "forecast"}
        )]
    except Exception as e:
        print(f"Forecast error: {e}")
        return []


def fetch_all_cost_data():
    """Fetch all cost related data."""
    docs = []
    print("Fetching monthly cost by service...")
    docs.extend(fetch_monthly_cost_by_service())
    print("Fetching total monthly cost...")
    docs.extend(fetch_total_monthly_cost())
    print("Fetching cost forecast...")
    docs.extend(fetch_cost_forecast())
    print(f"Cost fetcher done — {len(docs)} documents")
    return docs


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    docs = fetch_all_cost_data()
    print(f"\nTotal docs: {len(docs)}")
    print("\nSample:")
    for doc in docs[:3]:
        print(f"\n{doc.page_content}")
        print(f"Metadata: {doc.metadata}")