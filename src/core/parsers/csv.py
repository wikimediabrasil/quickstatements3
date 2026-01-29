import re
import csv
import io
from typing import Iterator
import logging

from .base import BaseParser
from .base import ParserException

from core.models import BatchCommand


logger = logging.getLogger(__name__)


class CSVCommandParser(BaseParser):
    ADD_WHAT_OP = {
        "alias": BatchCommand.Operation.ADD_ALIAS,
        "description": BatchCommand.Operation.SET_DESCRIPTION,
        "label": BatchCommand.Operation.SET_LABEL,
        "statement": BatchCommand.Operation.SET_STATEMENT,
        "sitelink": BatchCommand.Operation.SET_SITELINK,
    }
    REMOVE_WHAT_OP = {
        "alias": BatchCommand.Operation.REMOVE_ALIAS,
        "description": BatchCommand.Operation.REMOVE_DESCRIPTION,
        "label": BatchCommand.Operation.REMOVE_LABEL,
        "statement": BatchCommand.Operation.REMOVE_STATEMENT_BY_VALUE,
        "sitelink": BatchCommand.Operation.REMOVE_SITELINK,
    }

    def parse_line(self, row, header):
        commands = []
        current_command = None
        current_property = None
        current_action = None
        current_what = None
        current_summary = None
        qid = None
        entity_type = None

        for index, cell in enumerate(row):
            cell_value = cell.strip()
            debuginfo = f"Column {index}: {cell_value}"
            current_value = self.parse_value(cell_value)
            if current_value is None:
                current_value = {"type": "string", "value": cell_value}

            header_value = header[index]  # HEADER VALUE

            if index == 0:  # That is the QID, alway in the firs column
                if not cell_value:
                    # Our qid is empty, so it means we are creating a new item
                    commands.append({"action": "create", "type": "item"})
                    qid = "LAST"
                    entity_type = self.get_entity_type(qid)
                else:
                    # Just modifying and existing one
                    qid = cell_value
                    entity_type = self.get_entity_type(qid)

            elif not cell_value:
                continue  # Empty, does nothing

            elif header_value == "#":
                # Our header indicates that this column represents comments
                # We add the cell value to the last command created
                if not current_summary:
                    current_summary = cell_value
                else:
                    current_summary += cell_value
                current_command["summary"] = current_summary
                continue

            elif header_value.startswith("qal"):
                # Our header indicates that this column represents a qualifier
                # We add the cell value to the last command created
                qualifier = {
                    "property": header_value.replace("qal", "P"),
                    "value": current_value,
                }
                qualifiers = current_command.get("qualifiers", [])
                qualifiers.append(qualifier)
                current_command["qualifiers"] = qualifiers
                continue

            elif re.match("^[Ss]\\d+$", header_value):
                # Our header indicates that this column represents a source
                # We add the cell value to the last command created
                reference = {"property": "P" + header_value[1:], "value": current_value}

                if header_value[0] == "S":
                    previous_references = [reference]
                    references = current_command.get("references", [])
                    references.append(previous_references)
                    current_command["references"] = references
                else:
                    previous_references.append(reference)

            else:
                # Checking action
                if header_value[0] == "-":
                    action = "remove"
                    header_value = header_value[1:]
                else:
                    action = "add"

                _type = self.get_entity_type(header_value)
                if _type in ["property", "alias", "description", "label", "sitelink"]:
                    # NEW STATEMENT STARTING...

                    current_summary = None

                    if _type == "property":
                        # We have a property based statement
                        current_property = header_value
                        current_action = action
                        current_what = "statement"

                        current_command = {
                            "action": current_action,
                            "what": current_what,
                            "entity": {"type": entity_type, "id": qid},
                            "property": current_property,
                            "value": current_value,
                        }

                    else:
                        # ALIAS, DESCRIPTION, SITELINK or LABEL
                        current_action = action
                        current_what = _type
                        lang = header_value[1:]
                        current_command = {
                            "action": action,
                            "what": current_what,
                            "item": qid,
                            "value": current_value,
                        }
                        if current_what == "sitelink":
                            current_command["site"] = lang
                        else:
                            current_command["language"] = lang
                        # Code expects aliases to be a list of alias, like in v1
                        if current_command["what"] == "alias":
                            current_command["value"]["type"] = "aliases"
                            current_command["value"]["value"] = [
                                current_command["value"]["value"]
                            ]

                    commands.append((debuginfo, current_command))

        return commands

    def check_header(self, header):
        """
        Validates header
        """
        has_property_alias_description_label_sitelink = False
        for index, cell in enumerate(header):
            if index == 0:
                if cell != "qid":
                    raise ParserException("CSV header first element must be qid")
                continue

            # Is it a PROPERTY?
            clean_cell = cell[1:] if cell[0] == "-" else cell
            _type = self.get_entity_type(clean_cell)
            if _type in ["alias", "description", "label", "sitelink", "property"]:
                has_property_alias_description_label_sitelink = True
                continue

            # Not a property...lets check if we already have one
            if not has_property_alias_description_label_sitelink:
                if clean_cell == "#":
                    raise ParserException("A valid property must precede a comment")
                elif clean_cell.startswith("qal"):
                    raise ParserException("A valid property must precede a qualifier")
                elif (clean_cell[0] == "s" or clean_cell[0] == "S") and re.match(
                    "^[Ss]\\d+$", clean_cell
                ):
                    raise ParserException("A valid property must precede a source")
        return True

    def parse(self, raw_csv) -> Iterator[BatchCommand]:
        memory_file = io.StringIO(raw_csv, newline="")

        first_line = True
        reader = csv.reader(memory_file, delimiter=",")
        index = 0

        for row in reader:
            if first_line:
                self.check_header(row)
                header = row
                first_line = False
            else:
                commands = self.parse_line(row, header)
                for debuginfo, command in commands:
                    action = BatchCommand.ACTION_CREATE
                    operation = None
                    if command["action"] == "add":
                        action = BatchCommand.ACTION_ADD
                        what = command.get("what")
                        operation = self.ADD_WHAT_OP[what]
                    elif command["action"] == "remove":
                        action = BatchCommand.ACTION_REMOVE
                        what = command.get("what")
                        operation = self.REMOVE_WHAT_OP[what]
                    elif command["action"] == "create":
                        action = BatchCommand.ACTION_CREATE
                        if command["type"] == "item":
                            operation = BatchCommand.Operation.CREATE_ITEM
                        elif command["type"] == "property":
                            operation = BatchCommand.Operation.CREATE_PROPERTY
                    else:
                        action = BatchCommand.ACTION_MERGE

                    user_summary = command.pop("summary", None)

                    logger.debug(f"Parsed line {row}")

                    yield BatchCommand(
                        index=index,
                        json=command,
                        raw=debuginfo,
                        action=action,
                        operation=operation,
                        status=BatchCommand.STATUS_INITIAL,
                        user_summary=user_summary,
                    )
                    index += 1
