"""Turn a SingleFile document into an inert fragment before storing or displaying it."""
import base64
from collections import Counter
from html import escape

import html5lib
from django.core.exceptions import ValidationError

LIMIT = 2 * 1024 * 1024
BLOCKS = set("p br div span h1 h2 h3 h4 h5 h6 table caption thead tbody tfoot tr td th strong b em i u hr blockquote ul ol li pre code section article img".split())
DROP = set("head script style form input button textarea select iframe object embed svg math template noscript audio video canvas".split())


def raster(source):
    for mime, signature in (("image/png", b"\x89PNG\r\n\x1a\n"), ("image/jpeg", b"\xff\xd8\xff"), ("image/gif", b"GIF8")):
        prefix = f"data:{mime};base64,"
        if source.startswith(prefix):
            try:
                data = base64.b64decode(source[len(prefix):], validate=True)
            except ValueError:
                return ""
            return source if data.startswith(signature) else ""
    return ""


def fragment(source):
    if len(source.encode("utf-8")) > LIMIT:
        raise ValidationError("Максимальный размер одного документа — 2 МиБ.")
    removed = Counter()
    root = html5lib.parse(source, namespaceHTMLElements=False)

    def walk(node, depth=0):
        if depth > 100:
            raise ValidationError("Документ содержит слишком много вложенных элементов.")
        tag = node.tag
        if not isinstance(tag, str) or tag in DROP or tag.startswith("{"):
            if isinstance(tag, str):
                removed[tag.rsplit("}", 1)[-1]] += 1
            return ""
        if tag == "img":
            src = raster(node.get("src", ""))
            if src:
                return '<img src="' + src + '" alt="">'
            removed["img"] += 1
            return ""
        content = escape(node.text or "") + "".join(walk(child, depth + 1) + escape(child.tail or "") for child in node)
        if tag not in BLOCKS:
            if tag not in {"html", "body"}:
                removed[tag] += 1
            return content
        if node.attrib:
            removed["атрибуты"] += len(node.attrib)
        return f"<{tag}>" if tag in {"br", "hr"} else f"<{tag}>{content}</{tag}>"

    return walk(root), removed
