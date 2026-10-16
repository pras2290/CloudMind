import logging
from datetime import datetime, timedelta
from langchain_core.documents import Document
from fetchers.common import AWS_ERRORS, get_boto3_client, record_fetch_failure

logger = logging.getLogger(__name__)


def _get_cost_and_usage_all_pages(client, **kwargs):
    """Collect ResultsByTime across all NextPageToken pages."""
    results = []
    while True:
        response = client.get_cost_and_usage(**kwargs)
        results.extend(response["ResultsByTime"])
        token = response.get("NextPageToken")
        if not token:
            return results
        kwargs["NextPageToken"] = token


def fetch_monthly_cost_by_service():
    """Fetch last 6 months cost grouped by service."""
    end = datetime.today().replace(day=1).strftime("%Y-%m-%d")
    start = (datetime.today().replace(day=1) - timedelta(days=180)).strftime("%Y-%m-%d")

    docs = []
    try:
        client = get_boto3_client("ce")
        results = _get_cost_and_usage_all_pages(
            client,
            TimePeriod={"Start": start, "End": end},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}]
        )
    except AWS_ERRORS as e:
        record_fetch_failure("aws_cost_explorer", "monthly cost by service", e)
        return docs

    for result in results:
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
    end = datetime.today().replace(day=1).strftime("%Y-%m-%d")
    start = (datetime.today().replace(day=1) - timedelta(days=180)).strftime("%Y-%m-%d")

    docs = []
    try:
        client = get_boto3_client("ce")
        results = _get_cost_and_usage_all_pages(
            client,
            TimePeriod={"Start": start, "End": end},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"]
        )
    except AWS_ERRORS as e:
        record_fetch_failure("aws_cost_explorer", "total monthly cost", e)
        return docs

    for result in results:
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
    start = datetime.today().strftime("%Y-%m-%d")
    end = (datetime.today().replace(day=1) + timedelta(days=32)).replace(day=1).strftime("%Y-%m-%d")

    try:
        client = get_boto3_client("ce")
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
        # Forecasts routinely fail (e.g. not enough history); not a fetch failure.
        logger.warning("Forecast error: %s", e)
        return []


def fetch_all_cost_data():
    """Fetch all cost related data."""
    docs = []
    logger.info("Fetching monthly cost by service...")
    docs.extend(fetch_monthly_cost_by_service())
    logger.info("Fetching total monthly cost...")
    docs.extend(fetch_total_monthly_cost())
    logger.info("Fetching cost forecast...")
    docs.extend(fetch_cost_forecast())
    logger.info("Cost fetcher done — %d documents", len(docs))
    return docs


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    docs = fetch_all_cost_data()
    logger.info("\nTotal docs: %d", len(docs))
    logger.info("\nSample:")
    for doc in docs[:3]:
        logger.info("\n%s", doc.page_content)
        logger.info("Metadata: %s", doc.metadata)
