import csv
import chess.pgn
import chess.engine
from enum import Enum
from typing import List, Dict
import asyncio
import json
import sys
import os

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


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


engine_path = os.path.join(os.getcwd(), "models", "stockfish_14_x64_avx2.exe")
csv_path = os.path.join(os.getcwd(), "assets", "opening_book.csv")
opening_book = load_opening_book(csv_path)


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

FORCED_WIN_THRESHOLD = 500
MISS_CENTIPAWN_LOSS = 300
MISS_MATE_THRESHOLD = 3
ENDGAME_MATERIAL_THRESHOLD = 24
QUEEN_VALUE = 9

def detect_game_phase(board: chess.Board, in_opening: bool) -> GamePhase:
    if in_opening:
        return GamePhase.OPENING
    total_material = sum(
        len(board.pieces(p, color)) * {1: 1, 2: 3, 3: 3, 4: 5, 5: QUEEN_VALUE}[p]
        for color in [chess.WHITE, chess.BLACK] for p in chess.PIECE_TYPES if p != chess.KING
    )
    queens = sum(len(board.pieces(chess.QUEEN, color)) for color in [chess.WHITE, chess.BLACK])
    return GamePhase.ENDGAME if total_material <= ENDGAME_MATERIAL_THRESHOLD or (queens == 0 and total_material <= ENDGAME_MATERIAL_THRESHOLD * 2) else GamePhase.MIDDLEGAME

def is_book_move(board, opening_book, max_depth=8):  
    return None if board.fullmove_number > max_depth else opening_book.get(" ".join(board.fen().split()[:4]))

async def analyze_pgn(pgn_file: str):
    with open(pgn_file) as pgn:
        game = chess.pgn.read_game(pgn)
    if not game:
        return json.dumps({"error": "No game found in PGN file."})
    
    results = {
        "moves": [],
        "phases": {},
        "players": {"white": {}, "black": {}}
    }
    
    with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
        board = game.board()
        classifications = {"white": {p.value: [] for p in GamePhase}, "black": {p.value: [] for p in GamePhase}}
        in_opening = True

        for move_number, node in enumerate(game.mainline(), start=1):
            pre_info = engine.analyse(board, chess.engine.Limit(depth=20))
            pre_eval = pre_info["score"].white().score(mate_score=10000) or 0
            best_move = pre_info.get("pv", [None])[0]
            move = node.move
            board.push(move)
            post_info = engine.analyse(board, chess.engine.Limit(depth=20))
            post_eval = post_info["score"].white().score(mate_score=10000) or 0
            book_move = is_book_move(board, opening_book)
            current_phase = detect_game_phase(board, in_opening)
            if not book_move and in_opening:
                in_opening = False
            eval_loss = abs(pre_eval - post_eval)
            classification = Classification.BOOK if book_move else Classification.BLUNDER
            player = "white" if board.turn == chess.BLACK else "black"
            classifications[player][current_phase.value].append(classification.value)
            results["moves"].append({
                "move_number": move_number,
                "player": player,
                "move": move.uci(),
                "evaluation": post_eval / 100,
                "evaluation_loss": eval_loss / 100,
                "classification": classification.value
            })

        for phase in GamePhase:
            results["phases"][phase.value] = {
                "white": classifications["white"][phase.value],
                "black": classifications["black"][phase.value]
            }
        results["players"]["white"] = classifications["white"]
        results["players"]["black"] = classifications["black"]
    
    return json.dumps(results, indent=4)
