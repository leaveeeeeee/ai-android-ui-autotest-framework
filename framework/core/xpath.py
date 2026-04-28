from __future__ import annotations


def xpath_literal(value: str) -> str:
    """把任意字符串转换成安全 XPath 字符串字面量。"""

    if '"' not in value:
        return f'"{value}"'
    if "'" not in value:
        return f"'{value}'"

    parts = value.split('"')
    return "concat(" + ", '\"', ".join(f'"{part}"' for part in parts) + ")"
