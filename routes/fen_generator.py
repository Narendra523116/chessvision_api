import json

FEN_MAPPING = {
    "black-pawn": "p", "black-rook": "r", "black-knight": "n", "black-bishop": "b", "black-queen": "q", "black-king": "k",
    "white-pawn": "P", "white-rook": "R", "white-knight": "N", "white-bishop": "B", "white-queen": "Q", "white-king": "K"
}

# there are some issues in the code i,e in the line 87 , possible modification for that is   rank = int(grid_position[1]) - 1

# Grid settings
border = 0  
grid_size = 224  
block_size = grid_size // 8  

x_labels = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']  
y_labels = [8, 7, 6, 5, 4, 3, 2, 1]  

def get_grid_coordinate(pixel_x, pixel_y, perspective):
    try:
        adjusted_x = pixel_x - border
        adjusted_y = pixel_y - border

        if adjusted_x < 0 or adjusted_y < 0 or adjusted_x >= grid_size or adjusted_y >= grid_size:
            return None  

        x_index = adjusted_x // block_size
        y_index = adjusted_y // block_size

        if x_index < 0 or x_index >= len(x_labels) or y_index < 0 or y_index >= len(y_labels):
            return None  

        if perspective == "b":
            x_index = 7 - x_index  
            y_index = 7 - y_index  

        file = x_labels[x_index]
        rank = y_labels[y_index]

        return f"{file}{rank}"
    except Exception as e:
        print(f"Error in get_grid_coordinate: {e}")
        return None  

def gen_fen(result: dict, p: str, next_to_move : str):
    try:
        if not isinstance(result, dict):
            print("Error: Expected a dictionary for result")
            return None

        boxes = result.get("boxes", [])
        classes = result.get("classes", [])

        if not boxes or not classes:
            print("Error: Missing 'boxes' or 'classes' in input")
            return None

        if len(boxes) != len(classes):
            print("Error: Mismatch between bounding boxes and class labels")
            return None

        height, width = 224, 224  
        board = [["8"] * 8 for _ in range(8)]  

        for box, class_name in zip(boxes, classes):
            if not isinstance(box, (list, tuple)) or len(box) != 4:
                print(f"Skipping invalid box: {box}")
                continue  

            fen_piece = FEN_MAPPING.get(class_name, None)
            if not fen_piece:
                print(f"Skipping unrecognized piece: {class_name}")
                continue  

            try:
                x_min, y_min, x_max, y_max = map(int, box)
            except ValueError:
                print(f"Skipping box with invalid values: {box}")
                continue  

            center_x, center_y = (x_min + x_max) / 2, (y_min + y_max) / 2
            pixel_x = int(center_x)
            pixel_y = int(height - center_y)  

            grid_position = get_grid_coordinate(pixel_x, pixel_y, p)
            if grid_position:
                file = ord(grid_position[0]) - ord('a')
                rank = int(grid_position[1]) - 1

                if 0 <= rank < 8 and 0 <= file < 8:
                    board[rank][file] = fen_piece
                else:
                    print(f"Skipping out-of-bounds grid position: {grid_position}")

        fen_rows = []
        for row in board:
            fen_row = ""
            empty_count = 0
            for cell in row:
                if cell == "8":
                    empty_count += 1
                else:
                    if empty_count > 0:
                        fen_row += str(empty_count)
                        empty_count = 0
                    fen_row += cell
            if empty_count > 0:
                fen_row += str(empty_count)
            fen_rows.append(fen_row)  # FIXED: Ensured last row is added

        position_fen = "/".join(fen_rows)
        fen_notation = f"{position_fen}{next_to_move} - - 0 0"

        return fen_notation

    except Exception as e:
        print(f"Error in gen_fen: {e}")
        return None  
