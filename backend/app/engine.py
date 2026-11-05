"""O que todos os modos de jogo têm em comum."""


class RoomError(Exception):
    """Erro esperado, com mensagem pronta para mostrar ao jogador. Cada modo tem a sua subclasse."""
