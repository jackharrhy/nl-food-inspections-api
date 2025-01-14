from datetime import datetime


def extract_inspection_type_and_date(page):
    cropped_region = page.within_bbox(
        (0, 145, 160, page.height - 100)
    )  # Adjust x0, y0, x1, y1
    lines = cropped_region.extract_text_lines()

    values = []

    for i in range(0, len(lines), 2):
        text = lines[i]["text"]
        y_pos = lines[i]["top"]
        date = lines[i + 1]["text"] if i + 1 < len(lines) else None

        if not text.startswith("Food -"):
            raise ValueError(f"Expected text to start with 'Food -', but got: {text}")

        values.append(
            {
                "text": text.replace("Food - ", ""),
                "date": datetime.strptime(date, "%b %d, %Y"),
                "y_position": y_pos,
            }
        )

    return lines, values


def extract_text_from_bbox(page, x0, y0, x1, y1):
    cropped_region = page.within_bbox((x0, y0, x1, y1))
    lines = cropped_region.extract_text_lines()

    values = []

    for line in lines:
        values.append({"text": line["text"], "y_position": line["top"]})

    i = 0
    while i < len(values):
        current_group = [values[i]]
        next_idx = i + 1

        while next_idx < len(values):
            if (
                abs(values[next_idx]["y_position"] - values[next_idx - 1]["y_position"])
                < 15
            ):
                current_group.append(values[next_idx])
                next_idx += 1
            else:
                break

        if len(current_group) > 1:
            combined_text = " ".join(item["text"] for item in current_group)
            values[i] = {
                "text": combined_text,
                "y_position": current_group[0]["y_position"],
            }
            del values[i + 1 : next_idx]

        i += 1

    return lines, values


def extract_compliance_item_type(page):
    return extract_text_from_bbox(page, 160, 145, 230, page.height - 100)


def extract_compliance_item_description(page):
    return extract_text_from_bbox(page, 230, 145, 380, page.height - 100)


def extract_observation_and_corrective_actions(page):
    return extract_text_from_bbox(page, 380, 145, page.width - 50, page.height - 100)


def process_page(page):
    inspection_type_and_date_lines, inspection_type_and_date_values = (
        extract_inspection_type_and_date(page)
    )
    compliance_items_lines, compliance_items = extract_compliance_item_type(page)
    compliance_item_descriptions_lines, compliance_item_descriptions = (
        extract_compliance_item_description(page)
    )
    observation_and_corrective_actions_lines, observation_and_corrective_actions = (
        extract_observation_and_corrective_actions(page)
    )

    all_lines = [
        *inspection_type_and_date_lines,
        *compliance_items_lines,
        *compliance_item_descriptions_lines,
        *observation_and_corrective_actions_lines,
    ]

    records = []

    for action in observation_and_corrective_actions:
        action_y = action["y_position"]

        matching_inspection = None
        for inspection in inspection_type_and_date_values:
            if inspection["y_position"] <= action_y:
                if (
                    matching_inspection is None
                    or inspection["y_position"] > matching_inspection["y_position"]
                ):
                    matching_inspection = inspection

        matching_type = None
        for item_type in compliance_items:
            if item_type["y_position"] <= action_y:
                if (
                    matching_type is None
                    or item_type["y_position"] > matching_type["y_position"]
                ):
                    matching_type = item_type

        matching_description = None
        for description in compliance_item_descriptions:
            if description["y_position"] <= action_y:
                if (
                    matching_description is None
                    or description["y_position"] > matching_description["y_position"]
                ):
                    matching_description = description

        if matching_inspection and matching_type and matching_description:
            records.append(
                {
                    "inspection_type": matching_inspection["text"],
                    "inspection_date": matching_inspection["date"],
                    "compliance_type": matching_type["text"],
                    "description": matching_description["text"],
                    "observation": action["text"],
                }
            )

    for description in compliance_item_descriptions:
        desc_y = description["y_position"]

        already_included = False
        for action in observation_and_corrective_actions:
            if abs(action["y_position"] - desc_y) < 1:
                already_included = True
                break

        if not already_included:
            matching_inspection = None
            for inspection in inspection_type_and_date_values:
                if inspection["y_position"] <= desc_y:
                    if (
                        matching_inspection is None
                        or inspection["y_position"] > matching_inspection["y_position"]
                    ):
                        matching_inspection = inspection

            matching_type = None
            for item_type in compliance_items:
                if item_type["y_position"] <= desc_y:
                    if (
                        matching_type is None
                        or item_type["y_position"] > matching_type["y_position"]
                    ):
                        matching_type = item_type

            if matching_inspection and matching_type:
                records.append(
                    {
                        "inspection_type": matching_inspection["text"],
                        "inspection_date": matching_inspection["date"],
                        "compliance_type": matching_type["text"],
                        "description": description["text"],
                        "observation": None,
                    }
                )

    return all_lines, records


def debug_page(page):
    im = page.to_image(resolution=150)
    all_lines, records = process_page(page)
    im.draw_rects(all_lines)
    for record in records:
        import json

        print(json.dumps(record, indent=2, default=str))
    return im
