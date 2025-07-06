import argparse
import os
import glob
from dotenv import load_dotenv
from report_service import ReportService
from transactions_parser import AITransactionsParserService
from logger import logger


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_file", help="PDF filename (ex: santander_2025-05.pdf)")
    parser.add_argument("--bank", default="SANTANDER", help="Bank name (default: SANTANDER)")
    parser.add_argument("--currency", default="UY$", help="Currency (default: UY$)")
    parser.add_argument("--month", help="Month in format YYYY-MM (ej: 2025-05)")
    parser.add_argument("--send-email", action="store_true", help="Send report by email")    
    return parser.parse_args()


def get_matching_json_files(bank: str, currency: str) -> list:
    pattern = f"data/{bank}_*_{currency}.json"
    matching_files = glob.glob(pattern)
    matching_files.sort()
    return matching_files


def main():
    load_dotenv()
    args = get_args()

    pdf_path = f"pdfs/{args.pdf_file}"
    if not os.path.exists(pdf_path):
        logger.error(f"El archivo PDF no existe: {pdf_path}")
        return

    if not args.month:
        filename = args.pdf_file.replace(".pdf", "")
        parts = filename.split("_")
        if len(parts) >= 2:
            args.month = parts[-1]
        else:
            logger.error("Error parsing month.")
            return
    
    pdf_password = os.getenv("CI_PASSW_PDF")
    google_ai_api_key = os.getenv("GOOGLE_AI_API_KEY")
    
    if not pdf_password or not google_ai_api_key:
        logger.error("Missing env variables")
        return

    parser = AITransactionsParserService(
        bank_name=args.bank,
        currency=args.currency,
        month=args.month,
        pdf_path=pdf_path,
        google_ai_api_key=google_ai_api_key,
        pdf_password=pdf_password
    )

    json_output_path = f"data/{args.bank}_{args.month}_{args.currency}.json"

    _, _ = parser.get_transactions(json_output_path)

    json_files = get_matching_json_files(args.bank, args.currency)
    
    if not json_files:
        json_files = [json_output_path]
    print(json_files)
    report = ReportService(
        currency=args.currency,
        bank=args.bank,
        json_files=json_files
    )   
    report.generate(send_email=args.send_email)


if __name__ == "__main__":
    main()
