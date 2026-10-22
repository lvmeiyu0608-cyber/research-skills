#!/usr/bin/env python3
"""数据概况与前提初检（只读，不修改数据）。

用法:
  python scripts/data_profile.py --data data.csv [--vars y x1 x2] \
      [--id firm_id --time year] [--corr-threshold 0.8] [--output profile.json]

支持 .csv / .tsv / .xlsx / .xls / .dta / .sav / .parquet。
只做描述性检查：不删除、不填补、不变换任何数据。
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def load(path: Path) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(path)
    if ext == ".tsv":
        return pd.read_csv(path, sep="\t")
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path)
    if ext == ".dta":
        return pd.read_stata(path)
    if ext == ".sav":
        return pd.read_spss(path)
    if ext == ".parquet":
        return pd.read_parquet(path)
    sys.exit(f"不支持的文件格式: {ext}")


def r(x, d=4):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    return round(float(x), d)


def guess_type(s: pd.Series) -> str:
    v = s.dropna()
    if v.empty:
        return "all_missing"
    if not pd.api.types.is_numeric_dtype(s):
        return "categorical/text"
    u = v.unique()
    if set(np.unique(u)).issubset({0, 1}):
        return "binary(0/1)"
    if np.all(np.mod(v, 1) == 0):
        if v.min() >= 0 and len(u) > 10:
            return "count/integer"
        if len(u) <= 10:
            return "ordinal_or_categorical(<=10 levels)"
    return "continuous"


def profile_var(s: pd.Series) -> dict:
    out = {
        "dtype": str(s.dtype),
        "guessed_type": guess_type(s),
        "n_nonmissing": int(s.notna().sum()),
        "missing_rate": r(s.isna().mean()),
        "n_unique": int(s.nunique()),
    }
    if pd.api.types.is_numeric_dtype(s) and s.notna().any():
        v = s.dropna().astype(float)
        q1, q3 = v.quantile([0.25, 0.75])
        iqr = q3 - q1
        out.update({
            "mean": r(v.mean()), "sd": r(v.std()), "min": r(v.min()),
            "p25": r(q1), "median": r(v.median()), "p75": r(q3), "max": r(v.max()),
            "skewness": r(v.skew()), "kurtosis": r(v.kurt()),
            "share_zero": r((v == 0).mean()),
            "n_outliers_iqr3": int(((v < q1 - 3 * iqr) | (v > q3 + 3 * iqr)).sum()),
            "sentinel_codes": sentinel_counts(s),
        })
    else:
        out["top_values"] = {str(k): int(c) for k, c in s.value_counts().head(5).items()}
    return out


SENTINELS = [-999, -99, -9, -9999, -99999, 999, 9999, 99999, -1e10, 1e10]


def sentinel_counts(s: pd.Series) -> dict:
    """常见缺失码（-999、9999 等）出现次数；只计数，不替换。"""
    if not pd.api.types.is_numeric_dtype(s):
        return {}
    v = s.dropna()
    return {str(int(c)) if float(c).is_integer() else str(c): int((v == c).sum())
            for c in SENTINELS if (v == c).any()}


def warnings_for(name: str, p: dict) -> list:
    w = []
    if p.get("sentinel_codes"):
        w.append(f"{name}: 疑似缺失码 {p['sentinel_codes']}，确认含义后再决定是否设为缺失（不要直接参与缩尾/计算）")
    if p.get("share_zero") is not None and p["share_zero"] > 0.5:
        w.append(f"{name}: {p['share_zero']:.0%} 的值为 0；若为核心解释变量，效应可能主要来自'有/无'的差异，需单独检验")
    if p["missing_rate"] and p["missing_rate"] > 0.05:
        w.append(f"{name}: 缺失率 {p['missing_rate']:.1%}，需检查缺失是否随机")
    if p.get("skewness") is not None and abs(p["skewness"]) > 2:
        w.append(f"{name}: 偏度 {p['skewness']}，分布明显偏态（是否取对数/缩尾需研究者决定）")
    if p.get("n_outliers_iqr3"):
        w.append(f"{name}: {p['n_outliers_iqr3']} 个极端值（超出 3×IQR），先核对是否录入错误")
    if p["guessed_type"].startswith(("count", "ordinal")) and (p.get("min") or 0) >= 0 \
            and (p.get("share_zero") or 0) > 0.3:
        w.append(f"{name}: 非负整数且零值占比 {p['share_zero']:.0%}；若为计数因变量，考虑负二项/零膨胀模型")
    if p["n_unique"] == 1:
        w.append(f"{name}: 只有一个取值，无法进入模型")
    return w


def panel_check(df, id_col, time_col) -> dict:
    dup = int(df.duplicated([id_col, time_col]).sum())
    per_id = df.groupby(id_col)[time_col].nunique()
    n_t = df[time_col].nunique()
    return {
        "n_entities": int(df[id_col].nunique()),
        "n_periods": int(n_t),
        "time_range": [str(df[time_col].min()), str(df[time_col].max())],
        "duplicate_id_time_pairs": dup,
        "balanced": bool((per_id == n_t).all()),
        "periods_per_entity": {"min": int(per_id.min()), "median": r(per_id.median()), "max": int(per_id.max())},
    }


def within_share(df, id_col, cols) -> dict:
    """组内变异占总变异的比例：FE 模型依赖组内变异。"""
    out = {}
    for c in cols:
        v = df[[id_col, c]].dropna()
        total = v[c].var()
        if not total:
            continue
        within = (v[c] - v.groupby(id_col)[c].transform("mean")).var()
        out[c] = r(within / total)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--vars", nargs="*", help="要检查的变量（默认全部）")
    ap.add_argument("--id", help="面板个体标识列")
    ap.add_argument("--time", help="面板时间列")
    ap.add_argument("--corr-threshold", type=float, default=0.8)
    ap.add_argument("--output", help="输出 JSON 路径（默认打印到屏幕）")
    a = ap.parse_args()

    df = load(Path(a.data))
    cols = a.vars or [c for c in df.columns if c not in (a.id, a.time)]
    missing_cols = [c for c in cols if c not in df.columns]
    if missing_cols:
        sys.exit(f"数据中找不到这些变量: {missing_cols}；现有变量: {list(df.columns)}")

    report = {
        "file": a.data,
        "note": "描述性检查，未对数据做任何删除、填补或变换",
        "n_rows": int(len(df)),
        "n_columns": int(df.shape[1]),
        "n_duplicate_rows": int(df.duplicated().sum()),
        "complete_cases_for_selected_vars": int(df[cols].dropna().shape[0]),
        "variables": {},
        "warnings": [],
    }
    for c in cols:
        p = profile_var(df[c])
        report["variables"][c] = p
        report["warnings"] += warnings_for(c, p)

    if report["n_duplicate_rows"]:
        report["warnings"].append(f"存在 {report['n_duplicate_rows']} 行完全重复记录")
    drop = len(df) - report["complete_cases_for_selected_vars"]
    if drop:
        report["warnings"].append(f"列表删除后将丢失 {drop} 行（{drop/len(df):.1%}），需说明缺失处理方式")

    num = [c for c in cols if pd.api.types.is_numeric_dtype(df[c]) and df[c].nunique() > 1]
    if len(num) >= 2:
        cm = df[num].corr()
        pairs = []
        for i, x in enumerate(num):
            for y in num[i + 1:]:
                v = cm.loc[x, y]
                if pd.notna(v) and abs(v) >= a.corr_threshold:
                    pairs.append({"var1": x, "var2": y, "r": r(v)})
        report["high_correlation_pairs"] = pairs
        for p in pairs:
            report["warnings"].append(f"{p['var1']} 与 {p['var2']} 相关 r={p['r']}，注意共线性或是否测量同一构念")
        try:
            from statsmodels.stats.outliers_influence import variance_inflation_factor
            X = df[num].dropna()
            X = (X - X.mean()) / X.std()
            X.insert(0, "const", 1.0)
            report["vif"] = {c: r(variance_inflation_factor(X.values, i)) for i, c in enumerate(X.columns) if c != "const"}
            for c, v in report["vif"].items():
                if v and v > 5:
                    report["warnings"].append(f"{c}: VIF={v}，存在共线性风险")
        except ImportError:
            report["vif"] = "未计算（未安装 statsmodels）"

    if a.id and a.time:
        report["panel"] = panel_check(df, a.id, a.time)
        report["panel"]["within_variation_share"] = within_share(df, a.id, num)
        if report["panel"]["duplicate_id_time_pairs"]:
            report["warnings"].append(f"面板中有 {report['panel']['duplicate_id_time_pairs']} 个重复的 id-time 组合")
        if not report["panel"]["balanced"]:
            report["warnings"].append("非平衡面板：检查样本流失是否有系统性")
        for c, s in report["panel"]["within_variation_share"].items():
            if s is not None and s < 0.1:
                report["warnings"].append(f"{c}: 组内变异仅占 {s:.0%}，固定效应估计可能不精确")

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if a.output:
        Path(a.output).parent.mkdir(parents=True, exist_ok=True)
        Path(a.output).write_text(text, encoding="utf-8")
        print(f"已写入 {a.output}；警告 {len(report['warnings'])} 条：")
        for w in report["warnings"]:
            print("  -", w)
    else:
        print(text)


if __name__ == "__main__":
    main()
