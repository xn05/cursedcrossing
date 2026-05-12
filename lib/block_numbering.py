"""
Block numbering system for developer tools.
Converts between block numbers (1-indexed from bottom-left) and tile coordinates (0-indexed from top-left).
"""


def block_number_to_coords(block_number, region_width, region_height):
    """
    Convert block number to tile coordinates.
    
    Block numbering starts from bottom-left, goes right, then up.
    For a 10x10 region:
    - Row 1 (bottom): blocks 1-10 (y=9, x=0-9)
    - Row 2: blocks 11-20 (y=8, x=0-9)
    - ...
    - Row 10 (top): blocks 91-100 (y=0, x=0-9)
    
    Args:
        block_number: 1-indexed block number
        region_width: width of region in tiles
        region_height: height of region in tiles
        
    Returns:
        (x, y) tile coordinates, or None if invalid
    """
    if block_number < 1 or block_number > region_width * region_height:
        return None
    
    # Convert to 0-indexed
    block_idx = block_number - 1
    
    # Calculate row and column in the numbering system
    row_from_bottom = block_idx // region_width
    col_from_left = block_idx % region_width
    
    # Convert to tile coordinates (top-left origin)
    x = col_from_left
    y = region_height - 1 - row_from_bottom
    
    return (x, y)


def coords_to_block_number(x, y, region_width, region_height):
    """
    Convert tile coordinates to block number.
    
    Args:
        x: tile x coordinate (0-indexed from left)
        y: tile y coordinate (0-indexed from top)
        region_width: width of region in tiles
        region_height: height of region in tiles
        
    Returns:
        1-indexed block number, or None if invalid
    """
    if x < 0 or x >= region_width or y < 0 or y >= region_height:
        return None
    
    # Convert y from top-origin to bottom-origin
    row_from_bottom = region_height - 1 - y
    
    # Calculate block number
    block_number = row_from_bottom * region_width + x + 1
    
    return block_number


def get_block_numbers_in_region(region_width, region_height):
    """
    Get all valid block numbers for a region.
    
    Returns:
        List of block numbers from 1 to (width * height)
    """
    return list(range(1, region_width * region_height + 1))
