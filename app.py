import os
import json
from typing import List, Dict, Tuple, Any
from abc import ABC, abstractmethod

import matplotlib.pyplot as plt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from dotenv import load_dotenv

import utils
from logger import logger


class Concept:
    PEDIDOS_YA = "PEDIDOSYA"
    UBER = "UBER"
    DEVOTO = "DEVOTO"
    MERPAGO = "MERPAGO"
    OTHER = "OTHER"


class Folders:
    INPUT = "input"
    JSON_DATA = "data"


def get_json_files(last_n_elements: int = None) -> List[str]:
    json_files = [file.replace(".json", "") for file in os.listdir(Folders.JSON_DATA) if file.endswith(".json")]
    json_files.sort()
    if last_n_elements:
        return json_files[-last_n_elements:]

    return json_files


class TransactionsParserService(ABC):
    def __init__(self, bank_name: str, currency: str, month: str):
        self.bank_name = bank_name
        self.currency = currency
        self.month = month

    @abstractmethod
    def get_transactions(self) -> Tuple[List[Dict[str, Any]], int]:
        """
        Returns a tuple of transactions (List) and total transactions (int)
        """
        ...


class TransactionsAIParserService(TransactionsParserService):
    ...



class TransactionsManualParserService(TransactionsParserService):
    """
    Logic to parse the monthly bank PDF data into JSON format
    """
    def __init__(self, data: str, bank_name: str, currency: str, month: str = None):
        self.data: List[str] = data.split("\n")
        self.bank_name: str = bank_name
        self.currency: str = currency
        self.month: str = month

        self.transactions: List[Dict[str, Any]] = None

    def __process_transactions(self):
        transactions = []

        for line in self.data:
            if not line:
                continue
            transaction_data = line.split(" ")
            last_index = len(transaction_data) - 1
            amount = transaction_data[-1]
            if "-" in amount:
                amount = amount.replace("-", "")
                amount = "-" + amount

            amount = float(
                amount.replace(".", "").replace(",", ".")
            )

            transactions.append({
                "date": transaction_data[0],
                "amount": amount,
                "concept": " ".join(transaction_data[2:last_index]),
            })
        self.transactions = transactions

    def __group_by_concept(self) -> Dict[str, float]:
        # agrupations = {key: 0.0 for key in Concept.__dict__ if not key.startswith("__")}
        agrupations = {
            Concept.PEDIDOS_YA: 0.0,
            Concept.UBER: 0.0,
            Concept.DEVOTO: 0.0,
            Concept.MERPAGO: 0.0,
            Concept.OTHER: 0.0,
        }

        for transaction in self.transactions:
            concept = transaction["concept"]

            if Concept.PEDIDOS_YA in concept:
                agrupations[Concept.PEDIDOS_YA] += transaction["amount"]
            elif Concept.UBER in concept:
                agrupations[Concept.UBER] += transaction["amount"]
            elif Concept.DEVOTO in concept:
                agrupations[Concept.DEVOTO] += transaction["amount"]
            elif Concept.MERPAGO in concept:
                agrupations[Concept.MERPAGO] += transaction["amount"]
            else:
                agrupations[Concept.OTHER] += transaction["amount"]

        return agrupations

    def __save_transactions_in_json(self):
        if not self.transactions:
            return

        json_str = json.dumps({
            "month": self.month,
            "str_month": utils.month_str_to_month_name(self.month),
            "bank": self.bank_name,
            "currency": self.currency,
            "transactions_total_amount": sum(trans["amount"] for trans in self.transactions),
            "transactions": self.transactions,
        }, indent=2)

        os.makedirs("data", exist_ok=True)

        filename = f"data/{self.bank_name}_{self.month}_{self.currency}.json"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(json_str)
        logger.info("Archivo guardado en: %s", filename)

    def main(self):
        logger.info("bank: %s, Currency: %s, Month: %s", self.bank_name, self.currency, self.month)
        self.__process_transactions()
        if not self.transactions:
            return

        logger.info(self.__group_by_concept())
        logger.info("Total: %s", str(sum(transaction["amount"] for transaction in self.transactions)))
        self.__save_transactions_in_json()


class ReportService:
    """
    Logic to generate a report for the last 6 months based on available history.
    Compare by concept grouping and send an email with the information.
    """
    def __init__(self, currency: str, bank: str):
        self.currency = currency.upper()
        self.bank = bank.upper()

    def get_data_from_json_files(self) -> List[Dict[str, Any]]:
        # filter: last six months
        json_data_files = get_json_files(last_n_elements=6)
        # filter: bank & currency configs
        json_data_files = [
            file for file in json_data_files if self.bank in file and self.currency in file
        ]
        data = []

        for file in json_data_files:
            path = f"{Folders.JSON_DATA}/{file}.json"
            try:
                with open(path, "r", encoding="utf-8") as f:
                    json_info = json.load(f)
                    data.append(json_info)
            except Exception as error:
                logger.error("Error leyendo %s:%s", path, str(error))
        return data

    def _get_agrupations_by_months_and_concepts(self, month_data: Dict[str, Any]):
        agrupations = {
            Concept.PEDIDOS_YA: 0.0,
            Concept.UBER: 0.0,
            Concept.DEVOTO: 0.0,
            Concept.MERPAGO: 0.0,
            Concept.OTHER: 0.0,
        }
        transactions = month_data["transactions"]

        for transaction in transactions:
            concept = transaction["concept"]

            if Concept.PEDIDOS_YA in concept:
                agrupations[Concept.PEDIDOS_YA] += transaction["amount"]
            elif Concept.UBER in concept:
                agrupations[Concept.UBER] += transaction["amount"]
            elif Concept.DEVOTO in concept:
                agrupations[Concept.DEVOTO] += transaction["amount"]
            elif Concept.MERPAGO in concept:
                agrupations[Concept.MERPAGO] += transaction["amount"]
            else:
                agrupations[Concept.OTHER] += transaction["amount"]

        return agrupations

    def get_agrupations_by_months_and_concepts(self) -> List[Dict[str, float]]:
        all_transactions_data = self.data
        data = []

        for month_data in all_transactions_data:
            data.append({
                "month": month_data["str_month"],
                "agrupations": self._get_agrupations_by_months_and_concepts(month_data),
            })

        # Create the plot
        plt.figure(figsize=(10, 6))

        # Get all the categories (assuming they are the same for all months)
        categories = data[0]["agrupations"].keys()

        # Plot the data for the category
        for category in categories:
            # Get the values for each month for the current category
            values = [entry["agrupations"][category] for entry in data]
            months = [entry["month"] for entry in data]
            
            plt.plot(months, values, marker="o", linestyle="-", label=category)

            # Add the text with the value next to each point
            for i, val in enumerate(values):
                plt.text(months[i], val, f"{val:,.1f}", fontsize=10, ha="left", va="bottom")

        plt.title("Evolución de Conceptos")
        plt.xlabel("Mes")
        plt.ylabel("Importe ($)")
        plt.xticks(rotation=45)

        plt.grid(True)
        plt.legend()

        # plt.tight_layout()
        # plt.show()
        plt.savefig("tmp/grafica.png")
        plt.close()
        return data

    def get_html_table(self, data: Dict[str, float]) -> str:
        html = """\
        <html>
        <body>
            <h3>Datos de {month}</h3>
            <table border="1">
            <tr>
                <th>Categoría</th>
                <th>Importe ($)</th>
            </tr>""".format(month=data["month"])

        for cat, value in data["agrupations"].items():
            formatted_value = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            html += """\
            <tr>
                <td>{cat}</td>
                <td>{value}</td>
            </tr>""".format(cat=cat, value=formatted_value)

        html += """\
            </table>
            <p>Adjunto se encuentra la gráfica de la evolución de conceptos en los ultimos 6 meses de historico.<>
        </body>
        </html>
        """
        return html

    def send_email(self, agg_categories_data: List[Dict[str, float]]):
        agrupations_current_month = agg_categories_data[-1]
        sender_email = os.getenv("SENDER_EMAIL")
        html_table = self.get_html_table(agrupations_current_month)

        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = os.getenv("RECEIVER_EMAIL")
        msg["Subject"] = f"Reporte mensual tarjetas de crédito - {self.bank}, {self.currency}"

        msg.attach(MIMEText(html_table, "html"))

        try:
            with open("tmp/grafica.png", "rb") as f:
                img = MIMEImage(f.read())
                img.add_header("Content-ID", "<grafica>")
                msg.attach(img)

            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(sender_email, os.getenv("PASSW_APPLICATION_EMAIL"))
                server.send_message(msg)
                logger.info("Email enviado")
        except Exception as e:
            logger.error(f"Error al enviar el correo: {e}")

    def main(self):
        self.data = self.get_data_from_json_files()
        agg_categories_data = self.get_agrupations_by_months_and_concepts()
        self.send_email(agg_categories_data)


def process_pending_files(manual: bool = True):
    """
    FileName: input/{bank}_{month}_{currency}.txt

    Examples:
        - input/BROU_2025-01_USD.txt
        - input/SCOTIABANK_2024-12_UY$.txt
    """
    files = [file for file in os.listdir(Folders.INPUT) if file.endswith(".txt")]

    if not files:
        logger.info("No files in %s", Folders.INPUT)
        return None

    json_files = get_json_files()

    for file_path in files:
        _file_path = file_path.replace(".txt", "").upper()

        if _file_path in json_files:
            logger.info("Archivo %s ya fue procesado. Se omite", _file_path)
            continue

        file_data = _file_path.split("_")
        bank_name = file_data[0]
        month = file_data[1]
        currency = file_data[2]

        with open(f"{Folders.INPUT}/{file_path}", "r", encoding="utf-8") as file:
            data = file.read()

        if manual:
            parser_service = TransactionsManualParserService(data, bank_name, currency, month)
        else:
            parser_service = TransactionsAIParserService(data, bank_name, currency, month)
        parser_service.main()


if __name__ == "__main__":
    load_dotenv()
    process_pending_files()
    report_service = ReportService(currency="UY$", bank="SANTANDER")
    report_service.main()
