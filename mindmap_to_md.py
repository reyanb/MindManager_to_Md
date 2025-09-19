import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from typing import Iterable, Optional


class MindmapConversionError(Exception):
    """Raised when a MindManager document cannot be converted."""


def get_topic_text(topic: ET.Element) -> Optional[str]:
    """Extract readable text from a MindManager topic element."""
    text_node = topic.find("./{*}Text")
    if text_node is None:
        return None

    plain_attr = text_node.get("PlainText")
    if plain_attr:
        return plain_attr.strip()

    plain_elem = text_node.find("./{*}PlainText")
    if plain_elem is not None and plain_elem.text:
        return plain_elem.text.strip()

    # Rich text is nested in paragraphs; concatenate fragments in order.
    paragraphs = []
    for paragraph in text_node.findall("./{*}Paragraph"):
        pieces = []
        # Some documents use nested Text nodes, others store text on the paragraph.
        for inner in paragraph.iterfind(".//{*}Text"):
            if inner.text and inner.text.strip():
                pieces.append(inner.text.strip())
        if not pieces and paragraph.text and paragraph.text.strip():
            pieces.append(paragraph.text.strip())
        if pieces:
            paragraphs.append(" ".join(pieces))

    if paragraphs:
        return "\n".join(paragraphs)

    if text_node.text and text_node.text.strip():
        return text_node.text.strip()

    return None


def iter_child_topics(topic: ET.Element) -> Iterable[ET.Element]:
    """Yield immediate child topics regardless of container tag."""
    containers = (
        "./{*}SubTopics/{*}Topic",
        "./{*}LeftTopicGroup/{*}Topic",
        "./{*}RightTopicGroup/{*}Topic",
        "./{*}FloatingTopics/{*}Topic",
    )
    for path in containers:
        for child in topic.findall(path):
            yield child


def walk_topic(topic: ET.Element, level: int, md_lines: list[str]) -> None:
    text = get_topic_text(topic)
    if text:
        md_lines.append(f"{'#' * max(level, 1)} {text}")

    for child in iter_child_topics(topic):
        walk_topic(child, level + 1, md_lines)


def gather_immediate_child_text(topic: ET.Element) -> list[str]:
    """Collect text for the direct children of a topic."""
    texts: list[str] = []
    for child in iter_child_topics(topic):
        text = get_topic_text(child)
        if text:
            texts.append(text)
    return texts


def get_topic_position(topic: ET.Element) -> Optional[tuple[float, float]]:
    """Return the (x, y) offset for a topic if available."""
    offset = topic.find("./{*}Offset")
    if offset is None:
        return None

    try:
        cx = float(offset.get("CX", "nan"))
        cy = float(offset.get("CY", "nan"))
    except ValueError:
        return None

    if any(map(lambda value: value != value, (cx, cy))):  # NaN check
        return None

    return cx, cy


def _cluster_indices(values: list[float], tolerance: float = 25.0) -> Optional[tuple[list[float], dict[int, int]]]:
    if not values:
        return None

    sorted_items = sorted(enumerate(values), key=lambda pair: pair[1])
    clusters: list[dict[str, object]] = []
    for index, value in sorted_items:
        if not clusters or value - clusters[-1]["center"] > tolerance:
            clusters.append({"center": value, "members": [index]})
        else:
            cluster = clusters[-1]
            members = cluster["members"]  # type: ignore[assignment]
            members.append(index)
            cluster["center"] = (
                (cluster["center"] * (len(members) - 1) + value)  # type: ignore[operator]
                / len(members)
            )

    centers = [cluster["center"] for cluster in clusters]
    mapping: dict[int, int] = {}
    for cluster_index, cluster in enumerate(clusters):
        for member in cluster["members"]:  # type: ignore[assignment]
            mapping[member] = cluster_index

    return centers, mapping


def render_canvas_table(central_title: Optional[str], topics: list[ET.Element]) -> Optional[list[str]]:
    positions: list[tuple[float, float]] = []
    valid_topics: list[ET.Element] = []
    for topic in topics:
        text = get_topic_text(topic)
        if not text:
            continue
        pos = get_topic_position(topic)
        if pos is None:
            continue
        valid_topics.append(topic)
        positions.append(pos)

    if len(valid_topics) < 2:
        return None

    xs = [pos[0] for pos in positions]
    ys = [pos[1] for pos in positions]

    col_cluster = _cluster_indices(xs)
    row_cluster = _cluster_indices(ys)
    if not col_cluster or not row_cluster:
        return None

    col_centers, col_map = col_cluster
    row_centers, row_map = row_cluster

    n_cols = len(col_centers)
    n_rows = len(row_centers)

    if n_cols < 2 or n_rows < 2:
        return None

    table: list[list[list[ET.Element]]] = [
        [list() for _ in range(n_cols)] for _ in range(n_rows)
    ]

    for idx, topic in enumerate(valid_topics):
        row = row_map[idx]
        col = col_map[idx]
        table[row][col].append(topic)

    # Sort rows top→bottom and columns left→right
    row_order = sorted(range(n_rows), key=lambda i: row_centers[i])
    col_order = sorted(range(n_cols), key=lambda i: col_centers[i])

    # Pre-compute summaries for detection and rendering
    cell_data: list[list[dict[str, object]]] = []
    for row_idx in range(n_rows):
        row_cells: list[dict[str, object]] = []
        for col_idx in range(n_cols):
            topics_in_cell = table[row_idx][col_idx]
            entries: list[tuple[Optional[str], list[str]]] = []
            heading_count = 0
            child_count = 0
            for topic in topics_in_cell:
                heading = get_topic_text(topic)
                children = gather_immediate_child_text(topic)
                if heading:
                    heading_count += 1
                child_count += len(children)
                entries.append((heading, children))
            row_cells.append(
                {
                    "entries": entries,
                    "heading_count": heading_count,
                    "child_count": child_count,
                }
            )
        cell_data.append(row_cells)

    def extract_first_heading(entries: list[tuple[Optional[str], list[str]]]) -> Optional[str]:
        for heading, _ in entries:
            if heading:
                return heading
        return None

    def is_header_row(row_idx: int) -> bool:
        cells = [cell_data[row_idx][col_idx] for col_idx in col_order]
        heading_cells = sum(1 for cell in cells if cell["heading_count"] > 0)
        total_cells = len(cells)
        if heading_cells < max(2, total_cells // 2):
            return False
        child_total = sum(cell["child_count"] for cell in cells)
        return child_total <= heading_cells * 2

    def is_header_column(col_idx: int, skip_row: Optional[int]) -> bool:
        relevant_cells = []
        for row_idx in row_order:
            if skip_row is not None and row_idx == skip_row:
                continue
            cell = cell_data[row_idx][col_idx]
            if cell["entries"]:
                relevant_cells.append(cell)
        if len(relevant_cells) < 2:
            return False
        heading_cells = sum(1 for cell in relevant_cells if cell["heading_count"] > 0)
        if heading_cells < max(1, len(relevant_cells) - 1):
            return False
        child_total = sum(cell["child_count"] for cell in relevant_cells)
        return child_total <= heading_cells

    header_row_idx = row_order[0]
    use_column_headers = is_header_row(header_row_idx)

    header_col_idx = col_order[0]
    use_row_headers = is_header_column(
        header_col_idx, header_row_idx if use_column_headers else None
    )

    body_rows = [idx for idx in row_order if not (use_column_headers and idx == header_row_idx)]
    if not body_rows:
        body_rows = row_order

    body_cols = (
        [idx for idx in col_order if idx != header_col_idx]
        if use_row_headers
        else col_order
    )
    if not body_cols:
        body_cols = col_order
        use_row_headers = False

    column_headers: list[str] = []
    if use_column_headers:
        for position, col_idx in enumerate(body_cols, start=1):
            entries = cell_data[header_row_idx][col_idx]["entries"]  # type: ignore[index]
            heading = extract_first_heading(entries)
            column_headers.append(heading or f"Column {position}")
    else:
        column_headers = [f"Column {pos + 1}" for pos in range(len(body_cols))]

    row_labels: dict[int, str] = {}
    if use_row_headers:
        for seq, row_idx in enumerate(body_rows, start=1):
            entries = cell_data[row_idx][header_col_idx]["entries"]  # type: ignore[index]
            heading = extract_first_heading(entries)
            row_labels[row_idx] = heading or f"Row {seq}"

    def format_entries(entries: list[tuple[Optional[str], list[str]]]) -> str:
        if not entries:
            return "—"
        lines: list[str] = []
        for heading, children in entries:
            if heading:
                lines.append(f"- {heading}")
                for child in children:
                    lines.append(f"  - {child}")
            else:
                for child in children:
                    lines.append(f"- {child}")
        return "<br>".join(lines) if lines else "—"

    lines: list[str] = []
    if central_title:
        lines.append(f"# {central_title}")

    header_cells: list[str] = []
    if use_row_headers:
        header_cells.append(" ")
    header_cells.extend(column_headers)
    header_line = "| " + " | ".join(header_cells) + " |"
    separator = "| " + " | ".join("---" for _ in header_cells) + " |"
    lines.extend([header_line, separator])

    for row_idx in body_rows:
        row_cells: list[str] = []
        if use_row_headers:
            row_cells.append(row_labels.get(row_idx, "—"))
        for col_idx in body_cols:
            entries = cell_data[row_idx][col_idx]["entries"]  # type: ignore[index]
            row_cells.append(format_entries(entries))
        if not row_cells:
            continue
        lines.append("| " + " | ".join(row_cells) + " |")

    return lines if len(lines) > 2 else None


def looks_like_board_layout(topics: list[ET.Element]) -> bool:
    if len(topics) < 4:
        return False

    names = [get_topic_text(topic) for topic in topics]
    if not all(names):
        return False

    unique_names = {name for name in names if name}
    if len(unique_names) < max(3, len(names) - 1):
        return False

    positions = [get_topic_position(topic) for topic in topics]
    positioned = sum(1 for pos in positions if pos is not None)
    if positioned < len(topics) // 2:
        return False

    child_counts = sum(1 for topic in topics if gather_immediate_child_text(topic))
    return child_counts >= len(topics) // 2


def sort_topics_by_position(topics: list[ET.Element]) -> list[ET.Element]:
    placed = []
    unplaced = []
    for index, topic in enumerate(topics):
        pos = get_topic_position(topic)
        if pos is None:
            unplaced.append((index, topic))
        else:
            x, y = pos
            placed.append((x, y, index, topic))

    placed.sort(key=lambda item: (item[0], item[1], item[2]))
    ordered = [item[3] for item in placed] + [item[1] for item in sorted(unplaced, key=lambda item: item[0])]
    return ordered


def render_board_sections(central_title: Optional[str], topics: list[ET.Element]) -> list[str]:
    ordered_topics = sort_topics_by_position(topics)

    lines: list[str] = []
    if central_title:
        lines.append(f"# {central_title}")

    for topic in ordered_topics:
        heading = get_topic_text(topic)
        if not heading:
            continue
        lines.append(f"## {heading}")
        children = gather_immediate_child_text(topic)
        for child_text in children:
            lines.append(f"- {child_text}")
        lines.append("")

    if lines and lines[-1] == "":
        lines.pop()

    return lines


def extract_markdown_lines(file_path: str) -> list[str]:
    """Return Markdown lines extracted from a MindManager document."""
    if not os.path.exists(file_path):
        raise MindmapConversionError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".mmap":
            with zipfile.ZipFile(file_path, "r") as archive:
                if "Document.xml" not in archive.namelist():
                    raise MindmapConversionError(
                        "Document.xml not found inside the .mmap file."
                    )
                with archive.open("Document.xml") as document:
                    tree = ET.parse(document)
        elif ext == ".xmmap":
            tree = ET.parse(file_path)
        else:
            raise MindmapConversionError("Unsupported file type. Use .mmap or .xmmap")
    except ET.ParseError as exc:
        raise MindmapConversionError(f"Failed to parse mind map XML: {exc}") from exc

    root = tree.getroot()

    central_topic = root.find(".//{*}OneTopic/{*}Topic")
    if central_topic is None:
        central_topic = root.find(".//{*}Topic")

    if central_topic is None:
        raise MindmapConversionError("No topics found in the mind map.")

    md_lines: list[str] = []
    top_level_topics = [topic for topic in iter_child_topics(central_topic)]

    canvas_lines = render_canvas_table(get_topic_text(central_topic), top_level_topics)
    if canvas_lines:
        md_lines = canvas_lines
    elif looks_like_board_layout(top_level_topics):
        md_lines = render_board_sections(get_topic_text(central_topic), top_level_topics)
    else:
        walk_topic(central_topic, level=1, md_lines=md_lines)

    if not md_lines:
        raise MindmapConversionError(
            "No topic text found in the mind map. Check your file content."
        )

    return md_lines


def parse_mindmap_to_markdown(file_path: str, output_file: Optional[str] = None) -> None:
    """Convert a MindManager mind map to Markdown and write it to disk."""
    try:
        md_lines = extract_markdown_lines(file_path)
    except MindmapConversionError as exc:
        print(str(exc))
        return

    if output_file is None:
        output_file = os.path.splitext(file_path)[0] + ".md"

    with open(output_file, "w", encoding="utf-8") as stream:
        stream.write("\n".join(md_lines))

    print(f"Markdown file created: {output_file}")

# CLI usage
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 mindmap_to_md.py <file.mmap or file.xmmap>")
    else:
        parse_mindmap_to_markdown(sys.argv[1])
