from fastapi import FastAPI, File, UploadFile, HTTPException
import os
import tempfile
import chess.pgn
import chess.engine
from enum import Enum
from typing import List, Dict
from datetime import datetime
import csv
import json
from fastapi.responses import JSONResponse
import asyncio
import sys
from routes.tex_based_review import review_chess_game, validate_json



if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

class GamePhase(Enum):
    OPENING = "opening"
    MIDDLEGAME = "middlegame"
    ENDGAME = "endgame"

class Classification(Enum):
    BRILLIANT = "brilliant"
    GREAT = "great"
    BEST = "best"
    EXCELLENT = "excellent"
    GOOD = "good"
    INACCURACY = "inaccuracy"
    MISTAKE = "mistake"
    MISS = "miss"
    BLUNDER = "blunder"
    BOOK = "book"
    FORCED = "forced"

classification_values = {
    Classification.BLUNDER: 0,
    Classification.MISTAKE: 0.2,
    Classification.MISS: 0.3,
    Classification.INACCURACY: 0.4,
    Classification.GOOD: 0.65,
    Classification.EXCELLENT: 0.9,
    Classification.BEST: 1,
    Classification.GREAT: 1,
    Classification.BRILLIANT: 1,
    Classification.BOOK: 1,
    Classification.FORCED: 1,
}

centipawn_classifications = [
    Classification.BEST,
    Classification.EXCELLENT,
    Classification.GOOD,
    Classification.INACCURACY,
    Classification.MISS,
    Classification.MISTAKE,
    Classification.BLUNDER,
]

# Analysis parameters
FORCED_WIN_THRESHOLD = 500
MISS_CENTIPAWN_LOSS = 300
MISS_MATE_THRESHOLD = 3
ENDGAME_MATERIAL_THRESHOLD = 24
QUEEN_VALUE = 9

def detect_game_phase(board: chess.Board, in_opening: bool) -> GamePhase:
    if in_opening:
        return GamePhase.OPENING
        
    total_material = 0
    queens = 0
    
    for color in [chess.WHITE, chess.BLACK]:
        for piece_type in chess.PIECE_TYPES:
            if piece_type == chess.KING:
                continue
                
            count = len(board.pieces(piece_type, color))
            value = {
                chess.PAWN: 1,
                chess.KNIGHT: 3,
                chess.BISHOP: 3,
                chess.ROOK: 5,
                chess.QUEEN: QUEEN_VALUE
            }[piece_type]
            
            total_material += count * value
            if piece_type == chess.QUEEN:
                queens += count

    endgame_conditions = [
        total_material <= ENDGAME_MATERIAL_THRESHOLD,
        queens == 0 and total_material <= ENDGAME_MATERIAL_THRESHOLD * 2,
    ]
    
    return GamePhase.ENDGAME if any(endgame_conditions) else GamePhase.MIDDLEGAME

def get_evaluation_loss_threshold(classif: Classification, prev_eval: float) -> float:
    prev_eval = abs(prev_eval)
    if classif == Classification.BEST:
        return max(0.0001 * prev_eval**2 + 0.0236 * prev_eval - 3.7143, 0)
    elif classif == Classification.EXCELLENT:
        return max(0.0002 * prev_eval**2 + 0.1231 * prev_eval + 27.5455, 0)
    elif classif == Classification.GOOD:
        return max(0.0002 * prev_eval**2 + 0.2643 * prev_eval + 60.5455, 0)
    elif classif == Classification.INACCURACY:
        return max(0.0002 * prev_eval**2 + 0.3624 * prev_eval + 108.0909, 0)
    elif classif == Classification.MISS:
        return max(0.00025 * prev_eval**2 + 0.38255 * prev_eval + 166.9541, 0)
    elif classif == Classification.MISTAKE:
        return max(0.0003 * prev_eval**2 + 0.4027 * prev_eval + 225.8182, 0)
    else:
        return float("inf")

def load_opening_book(csv_path):
    opening_book = {}
    try:
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            next(reader)
            for row in reader:
                if len(row) < 3:
                    continue
                pgn_moves = row[2]
                game = chess.pgn.Game()
                board = game.board()
                for move in pgn_moves.split():
                    if "." in move:
                        continue
                    try:
                        chess_move = board.push_san(move)
                        fen = " ".join(board.fen().split()[:4])
                        opening_book[fen] = chess_move.uci()
                    except ValueError:
                        break
    except Exception as e:
        print(f"Error loading opening book: {e}")
    return opening_book

def is_book_move(board, opening_book, max_depth=8):  
    if board.fullmove_number > max_depth:  
        return None  
    fen = " ".join(board.fen().split()[:4])
    return opening_book.get(fen)


engine_path = os.path.join(os.getcwd(), "models", "stockfish-windows-x86-64-avx2.exe")
book_csv_path = os.path.join(os.getcwd(), "assets", "openings_master.csv")

def analyze_pgn(pgn_file: str) -> Dict:
    opening_book = load_opening_book(book_csv_path)
    text_based_result = review_chess_game(pgn_file)
    
    with open(pgn_file) as pgn:
        game = chess.pgn.read_game(pgn)
    
    if not game:
        return {"error": "No game found in the PGN file."}
    
    result = {
        "move_analysis": [],
        "phase_analysis": {},
        "player_summaries": {},
        "test_based_review": text_based_result
    }
    
    with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
        board = game.board()
        classifications = {
            "white": {phase: [] for phase in GamePhase},
            "black": {phase: [] for phase in GamePhase}
        }
        phase_data = {phase: [] for phase in GamePhase}
        in_opening = True

        for move_number, node in enumerate(game.mainline(), start=1):
            # Analyze position before the move
            pre_info = engine.analyse(board, chess.engine.Limit(time=0.3), multipv=3)[0]

            pre_eval = pre_info["score"].white().score(mate_score=10000) or 0

            pre_pv_moves = pre_info.get("pv", [])
            
            # Get best move and follow-up moves in UCI notation
            best_move_pre = pre_pv_moves[0].uci() if pre_pv_moves else None
            follow_up_pre = [m.uci() for m in pre_pv_moves[:min(len(pre_pv_moves), 5)]]

            # Make the user move
            move = node.move
            board.push(move)  # Update the board state

            # Analyze position after the move
            post_info = engine.analyse(board, chess.engine.Limit(time=0.3), multipv=3)[0]

            # Get best move and follow-up moves AFTER move is played (in UCI notation)
            post_pv_moves = post_info.get("pv", [])
            best_move_post = post_pv_moves[0].uci() if post_pv_moves else None
            follow_up_post = [m.uci() for m in post_pv_moves[:min(len(post_pv_moves), 5)]]

            post_eval = post_info["score"].white().score(mate_score=10000) or 0

            # Determine game phase
            book_move = is_book_move(board, opening_book)
            current_phase = detect_game_phase(board, in_opening)
            if not book_move and in_opening:
                in_opening = False

            # Calculate evaluation loss
            eval_loss = abs(pre_eval - post_eval)

            # Initial classification
            classification = Classification.BOOK if book_move else None
            if not classification:
                for classif in centipawn_classifications:
                    threshold = get_evaluation_loss_threshold(classif, pre_eval)
                    if eval_loss <= threshold:
                        classification = classif
                        break
                classification = classification or Classification.BLUNDER

            # Check for missed opportunities
            is_winning = abs(pre_eval) >= FORCED_WIN_THRESHOLD
            is_forced_win = pre_info["score"].is_mate() and pre_info["score"].relative.mate() <= MISS_MATE_THRESHOLD
            if is_winning and move != best_move_pre and (eval_loss >= MISS_CENTIPAWN_LOSS or is_forced_win):
                classification = Classification.MISS

            # Check for brilliant moves
            if classification == Classification.BEST:
                if pre_eval < -150 and post_eval >= 150:
                    classification = Classification.GREAT
                elif pre_eval < -300 and post_eval >= 300:
                    classification = Classification.BRILLIANT

            # Track classifications
            player = "white" if board.turn == chess.BLACK else "black"
            classifications[player][current_phase].append(classification)
            phase_data[current_phase].append(classification)

            # Add move analysis to result (using UCI notation)
            result["move_analysis"].append({
                "move_number": move_number,
                "player": "White" if board.turn == chess.BLACK else "Black",
                "user_move": move.uci(),
                "evaluation": post_eval / 100,
                "evaluation_loss": eval_loss / 100,
                "classification": classification.value,
                "best_move_pre": best_move_pre,  # Best move BEFORE move is played (UCI)
                "follow_up_pre": follow_up_pre,  # Follow-up moves BEFORE move is played (UCI)
                "best_move_post": best_move_post,  # Best move AFTER move is played (UCI)
                "follow_up_post": follow_up_post  # Follow-up moves AFTER move is played (UCI)
            })

        # Phase analysis
        for phase in GamePhase:
            moves = phase_data[phase]
            if moves:
                rating = get_phase_rating(moves)
                result["phase_analysis"][phase.value] = {
                    "rating": rating.value,
                    "move_count": len(moves)
                }

        # Player summaries
        for color in ["white", "black"]:
            player = game.headers["White" if color == "white" else "Black"]
            counts = {c.value: 0 for c in Classification}
            
            for phase in GamePhase:
                phase_moves = classifications[color][phase]
                for m in phase_moves:
                    m_enum = Classification(m) if isinstance(m, str) else m  # Convert if needed
                    counts[m_enum.value] += 1
            
            result["player_summaries"][player] = counts

    def convert_enums(obj):
        if isinstance(obj, Enum):  # Convert Enum to its value
            return obj.value
        if isinstance(obj, dict):  # Recursively handle dicts
            return {k: convert_enums(v) for k, v in obj.items()}
        if isinstance(obj, list):  # Recursively handle lists
            return [convert_enums(i) for i in obj]
        return obj  # Return other types as they are

    json_result = convert_enums(result)

    return JSONResponse(content=json_result)


def get_phase_rating(classified_moves: List[Classification]) -> Classification:

    if not classified_moves:
        return Classification.GOOD

    classified_moves = [Classification(m) if isinstance(m, str) else m for m in classified_moves]
        
    total = sum(classification_values[m] for m in classified_moves)
    average = total / len(classified_moves)
    
    rating_order = [
        (Classification.BRILLIANT, 0.95),
        (Classification.GREAT, 0.85),
        (Classification.BEST, 0.75),
        (Classification.EXCELLENT, 0.65),
        (Classification.GOOD, 0.5),
        (Classification.INACCURACY, 0.35),
        (Classification.MISS, 0.25),
        (Classification.MISTAKE, 0.15)
    ]
    
    return next((c for c, t in rating_order if average >= t), Classification.BLUNDER)