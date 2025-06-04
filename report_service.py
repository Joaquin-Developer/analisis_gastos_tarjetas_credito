import os
import json
from typing import List, Dict, Any

import matplotlib.pyplot as plt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from dotenv import load_dotenv

from logger import logger


class Concept:
    PEDIDOS_YA = "PEDIDOSYA"
    UBER = "UBER"
    DEVOTO = "DEVOTO"
    LAVOMAT = "LAVOMAT"
    MERPAGO = "MERPAGO"
    OTHER = "OTHER"


class ReportService:
    """
    Logic to generate a report for the last 6 months based on available history.
    Compare by concept grouping and send an email with the information.
    """
    def __init__(self, currency: str, bank: str, json_files: List[str]):
        self.currency = currency.upper()
        self.bank = bank.upper()
        self.json_files = json_files

    def get_data_from_json_files(self) -> List[Dict[str, Any]]:
        # filter: bank & currency configs
        # json_data_files = [
        #     file for file in self.json_files if self.bank in file and self.currency in file
        # ]
        json_data_files = self.json_files
        data = []

        for path in json_data_files:
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
            Concept.LAVOMAT: 0.0,
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
            elif Concept.LAVOMAT in concept:
                agrupations[Concept.LAVOMAT] += transaction["amount"]
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

    def get_html_table(self, data: Dict[str, Any]) -> str:
        html = """\
        <html>
        <head>
            <style>
                table {
                    border-collapse: collapse;
                    width: 50%;
                    margin-top: 10px;
                    font-family: Arial, sans-serif;
                }
                th, td {
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }
                th {
                    background-color: #f2f2f2;
                    font-weight: bold;
                }
                tr:nth-child(even) { background-color: #f9f9f9; }
            </style>
        </head>
        <body>
            <h3>Datos del ultimo mes ({**month**})</h3>
            <table border="1">
            <tr>
                <th>Categoría</th>
                <th>Importe ($)</th>
            </tr>
        """.replace("{**month**}", data["month"])

        for cat, value in data["agrupations"].items():
            formatted_value = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            html += """\
            <tr>
                <td>{cat}</td>
                <td>{value}</td>
            </tr>""".format(cat=cat, value=formatted_value)

        html += """\
            </table>
            <p>Adjunto se encuentra la gráfica de la evolución de conceptos en los ultimos 6 meses de historico.</p>
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

    def generate(self, send_email: bool = False):
        self.data = self.get_data_from_json_files()
        agg_categories_data = self.get_agrupations_by_months_and_concepts()

        if send_email:
            return self.send_email(agg_categories_data)
        print(agg_categories_data)


if __name__ == "__main__":
    load_dotenv()

    report = ReportService(
        currency="UY$",
        bank="SANTANDER",
        json_files=[
            "data/SANTANDER_2025-02_UY$.json",
            "data/SANTANDER_2025-03_UY$.json",
            "data/example_manual.json",
            "data/example_ai.json",
        ],
    )
    report.generate(send_email=True)
