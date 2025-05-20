from typing import List, Dict, Any

from .test_data import get_test_data


def parser_data_with_ai_v3() -> List[Dict[str, Any]]:
    try:
        from .test_data import get_test_data
        import json
        generated_data = get_test_data()
        generated_data = generated_data.replace("```json", "").replace("```", "")
        return json.loads(generated_data)
    except ImportError:
        import os
        from poc import TransactionsParserServicePOC
        file = "pdfs/santander_2025-03.pdf"
        ci_passw_pdf = os.getenv("CI_PASSW_PDF")
        google_ai_api_key = os.getenv("GOOGLE_AI_API_KEY")

        if not ci_passw_pdf or not google_ai_api_key:
            raise Exception("Missing env variables: 'CI_PASSW_PDF' and 'GOOGLE_AI_API_KEY'")

        tr_parser = TransactionsParserServicePOC(file, google_ai_api_key, ci_passw_pdf)
        transactions, total = tr_parser.get_transactions()
        print(f"Total Amount $: {total}")
        print(f"Total transactions: {len(transactions)}")


def parser_data_with_ai_v2() -> List[Dict[str, Any]]:
    import json
    generated_data = get_test_data()
    generated_data = generated_data.replace("```json", "").replace("```", "")
    return json.loads(generated_data)


def parser_data_with_manual_entrity() -> List[Dict[str, Any]]:
    import json
    path = "data/SANTANDER_2025-03_UY$.json"
    with open(path, "r", encoding="utf-8") as file:
        json_data = json.load(file)
    return json_data["transactions"]


def test_data_extract_ai_vs_manual_data():
    # ai_parser = parser_data_with_ai_v2()
    ai_parser = parser_data_with_ai_v3()
    manual_parser = parser_data_with_manual_entrity()
    assert len(ai_parser) == len(manual_parser)
