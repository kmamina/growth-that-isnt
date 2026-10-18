import duckdb
import pandas as pd
from config import RAW, ROOT

DB = ROOT / "data" / "zesto.duckdb"
SQL = (ROOT / "sql" / "01_dq_detection.sql").read_text()


def main():
    con = duckdb.connect(str(DB), read_only=True)
    parts = [s.strip() for s in SQL.split(";") if "SELECT" in s]
    rows = []
    for s in parts:
        r = con.execute(s).fetchone()
        rows.append(dict(issue_id=r[0], issue=r[1], detected=r[2]))
    det = pd.DataFrame(rows).sort_values("issue_id")

    log = pd.read_csv(RAW / "injection_log.csv")
    inj = log.groupby("issue_id").size().rename("injected").reset_index()
    out = det.merge(inj, on="issue_id", how="left")
    out["difference"] = out.detected - out.injected
    print(out.to_string(index=False))
    out.to_csv(ROOT / "reports" / "dq_detection_summary.csv", index=False)
    con.close()


if __name__ == "__main__":
    main()
    