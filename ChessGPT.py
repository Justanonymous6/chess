import chess
import chess.pgn
import openai

# Exception for bad player move
class badPlayerMoveError(Exception):
    pass

# Exception for bad bot move
class badGPTMoveError(Exception):
    pass

class GameState:
    def __init__(self):
        self.board = chess.Board()

    def makeMove(self, move):
        try:
            chess_move = self.board.parse_san(move)
            self.board.push(chess_move)
        except:
            raise badPlayerMoveError("Invalid move")

    def undoMove(self):
        self.board.pop()

class Move:
    def __init__(self, startSq, endSq, board):
        self.startRow = startSq[0]
        self.startCol = startSq[1]
        self.endRow = endSq[0]
        self.endCol = endSq[1]
        self.pieceMoved = board[self.startRow][self.startCol]
        self.pieceCaptured = board[self.endRow][self.endCol]

    def getChessNotation(self):
        # This method would return the move in standard chess notation (e.g., e2e4, Nf3, etc.)
        # For simplicity, let's just return a string combining start and end squares
        return f"{self.startRow}{self.startCol}{self.endRow}{self.endCol}"

class CastleRights:
    def __init__(self, wks, bks, wqs, bqs):
        self.wks = wks
        self.bks = bks
        self.wqs = wqs
        self.bqs = bqs

def printDebug(input, self):
    if self.printDebug:
        print(input)

class Game:
    def __init__(self, apiKey):
        openai.api_key = apiKey
        self.maxTokens = 10
        self.maxFails = 5
        self.prompt = {
            "normal": "Reply next chess move as {}. Only say the move. {}",
            "failed": "Reply next chess move as {}. Play one of these moves: {}. Only say the move. {}",
            "start": "Say the first move to play in chess in standard notation"
        }

        self.gameState = GameState()
        self.fails = 0
        self.message = ""
        self.printDebug = False

    def play(self, move):
        printDebug("play", self)
        if self.gameState.board.is_game_over():
            return

        self.pushPlayerMove(move)
        return self.getGPTMove()

    def pushPlayerMove(self, move):
        try:
            self.gameState.makeMove(move)
            return
        except badPlayerMoveError:
            raise badPlayerMoveError("The move inputted can't be played")

    def getGPTMove(self):
        printDebug("getGPTMove", self)
        if self.gameState.board.is_game_over():
            return

        for i in range(5):
            try:
                return self.handleResponse(self.askGPT(self.createPrompt()))
            except badGPTMoveError:
                pass

        self.message = f"Move fail limit reached ({self.fails})"
        return

    def createPrompt(self):
        printDebug("createPrompt", self)
        if self.gameState.board.turn == chess.WHITE:
            color = "white"
        else:
            color = "black"

        if self.gameState.board.board_fen() == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1":
            currPrompt = self.prompt["start"]
        elif self.fails != 0:
            currPrompt = self.prompt["failed"].format(
                color, str(self.gameState.board.legal_moves)[36:-1],
                str(chess.pgn.Game.from_board(self.gameState.board))[93:-2]
            )
        else:
            currPrompt = self.prompt["normal"].format(
                color, str(chess.pgn.Game.from_board(self.gameState.board))[93:-2]
            )
        printDebug(currPrompt, self)
        return currPrompt

    def askGPT(self, currPrompt) -> str:
        printDebug("askGPT", self)
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": currPrompt}
            ],
            max_tokens=self.maxTokens,
            temperature=0.7,
        )
        return response.choices[0]["message"]["content"]


    def handleResponse(self, completion):
        printDebug("handleCompletion", self)
        move = completion.replace("\n", "").replace(".", "").replace(" ", "")

        for i in range(len(move)):
            try:
                int(move[i])
            except ValueError:
                move = move[i:]
                break

        printDebug(move, self)

        if len(move) > 2:
            move = move[0].capitalize() + move[1:]

        try:
            self.gameState.makeMove(move)
            self.message = f"Move normal: {move} Fails: {self.fails}"
            self.fails = 0
            return move
        except:
            pass

        try:
            ModMove = move[0].lower() + move[1:]
            self.gameState.makeMove(ModMove)
            self.message = f"Move lower: {move} Fails: {self.fails}"
            self.fails = 0
            return move[0].lower() + move[1:]
        except:
            pass

        move = completion
        for chars in range(len(move), 0, -1):
            for i in range(len(move)):
                try:
                    self.gameState.makeMove(move[i:i + chars])
                    self.message = f"Move scan: {move[i:i + chars]} Fails: {self.fails}"
                    self.fails = 0
                    return move[i:i + chars]
                except:
                    pass

        self.fails += 1
        raise badGPTMoveError("The move ChatGPT gave can't be played")

