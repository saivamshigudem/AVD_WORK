import os
import requests

DEMO_FILES = {
    "Apple_2025_ESG_Report.pdf": "https://www.apple.com/environment/pdf/Apple_Environmental_Sustainability_Report_2022.pdf",
    "Google_2025_ESG_Report.pdf": "https://www.gstatic.com/policies/sustainability/google-sustainability-report-2024.pdf",
    "Microsoft_2025_ESG_Report.pdf": "https://query.prod.cms.rt.microsoft.com/cms/api/am/binary/RE4X8kQ"
}


def download_demo_reports(target_dir: str = "esg_reports"):
    os.makedirs(target_dir, exist_ok=True)
    for filename, url in DEMO_FILES.items():
        dest = os.path.join(target_dir, filename)
        if os.path.exists(dest):
            print(f"Skipping existing {filename}")
            continue
        try:
            print(f"Downloading {filename} from {url}")
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            with open(dest, "wb") as f:
                f.write(resp.content)
            print(f"Saved {dest}")
        except Exception as e:
            print(f"Failed to download {url}: {e}")


if __name__ == "__main__":
    download_demo_reports()
