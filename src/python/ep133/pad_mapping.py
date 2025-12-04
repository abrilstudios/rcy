"""EP-133 pad-to-node mapping utilities.

The EP-133 has a quirky mapping between physical pad numbers and filesystem
node IDs. Physical pads are numbered bottom-to-top (1-3 on bottom row),
but the filesystem stores them top-to-bottom (files 01-03 on top row).

Structure:
- 9 projects (1-9)
- 4 groups/banks per project (A, B, C, D)
- 12 pads per group

Node ID formula:
    node = 2000 + (project × 1000) + 100 + group_offset + file_num

Where:
    group_offset: A=100, B=200, C=300, D=400
    file_num: 1-12 (NOT the same as physical pad number!)
"""

# Group letter to offset mapping
GROUP_OFFSETS = {"A": 100, "B": 200, "C": 300, "D": 400}

# Physical pad number (1-12) → Filesystem file number (1-12)
# Pads are numbered bottom-to-top, files are stored top-to-bottom
#
# Physical layout:        Filesystem files:
#   10  11  12  (top)       01  02  03
#    7   8   9              04  05  06
#    4   5   6              07  08  09
#    1   2   3  (bottom)    10  11  12
#
PAD_TO_FILE = {
    1: 10, 2: 11, 3: 12,   # Bottom row (physical) → files 10-12
    4: 7,  5: 8,  6: 9,    # Row 2
    7: 4,  8: 5,  9: 6,    # Row 3
    10: 1, 11: 2, 12: 3,   # Top row (physical) → files 1-3
}

FILE_TO_PAD = {v: k for k, v in PAD_TO_FILE.items()}


def pad_to_node_id(project: int, group: str, pad: int) -> int:
    """Convert project/group/pad address to filesystem node ID.

    Args:
        project: Project number (1-9)
        group: Group/bank letter (A, B, C, or D)
        pad: Physical pad number (1-12)

    Returns:
        Node ID for use with device.assign_sound() or device.get_metadata()

    Raises:
        ValueError: If any argument is out of range

    Example:
        >>> pad_to_node_id(1, "A", 1)  # Project 1, Bank A, Pad 1
        3210  # = 2000 + 1000 + 100 + 100 + 10
    """
    if not (1 <= project <= 9):
        raise ValueError(f"Project must be 1-9, got {project}")
    group = group.upper()
    if group not in GROUP_OFFSETS:
        raise ValueError(f"Group must be A/B/C/D, got {group}")
    if not (1 <= pad <= 12):
        raise ValueError(f"Pad must be 1-12, got {pad}")

    file_num = PAD_TO_FILE[pad]
    project_node = 2000 + (project * 1000)  # 3000, 4000, ...
    groups_node = project_node + 100         # 3100, 4100, ...
    group_node = groups_node + GROUP_OFFSETS[group]  # 3200, 3300, ...
    return group_node + file_num


def node_id_to_pad_address(node_id: int) -> tuple[int, str, int] | None:
    """Convert node ID back to project/group/pad address.

    Args:
        node_id: Filesystem node ID

    Returns:
        Tuple of (project, group, pad) or None if not a valid pad node

    Example:
        >>> node_id_to_pad_address(3210)
        (1, 'A', 1)
    """
    for project in range(1, 10):
        project_node = 2000 + (project * 1000)
        groups_node = project_node + 100
        for group_letter, offset in GROUP_OFFSETS.items():
            group_node = groups_node + offset
            for file_num in range(1, 13):
                if group_node + file_num == node_id:
                    pad = FILE_TO_PAD[file_num]
                    return (project, group_letter, pad)
    return None


def format_pad_address(project: int, group: str, pad: int) -> str:
    """Format a pad address as a string like '1/A/1'."""
    return f"{project}/{group.upper()}/{pad}"


def parse_pad_address(address: str) -> tuple[int, str, int]:
    """Parse a pad address string like '1/A/1'.

    Args:
        address: String in format 'project/group/pad'

    Returns:
        Tuple of (project, group, pad)

    Raises:
        ValueError: If address format is invalid
    """
    parts = address.strip("/").split("/")
    if len(parts) != 3:
        raise ValueError(f"Invalid address format: {address}. Expected: project/group/pad")

    try:
        project = int(parts[0])
    except ValueError:
        raise ValueError(f"Invalid project number: {parts[0]}")

    group = parts[1].upper()
    if group not in GROUP_OFFSETS:
        raise ValueError(f"Invalid group: {parts[1]}. Must be A, B, C, or D")

    try:
        pad = int(parts[2])
    except ValueError:
        raise ValueError(f"Invalid pad number: {parts[2]}")

    return (project, group, pad)


# Sound slot category ranges (for reference/validation)
SLOT_CATEGORIES = {
    "KICK": (1, 99),
    "SNARE": (100, 199),
    "CYMB": (200, 299),
    "PERC": (300, 399),
    "BASS": (400, 499),
    "MELOD": (500, 599),
    "LOOP": (600, 699),
    "USER1": (700, 799),
    "USER2": (800, 899),
    "SFX": (900, 999),
}


def get_slot_category(slot: int) -> str | None:
    """Get the category name for a sound slot number."""
    for category, (start, end) in SLOT_CATEGORIES.items():
        if start <= slot <= end:
            return category
    return None
