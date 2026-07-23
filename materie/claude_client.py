"""
Client Anthropic condiviso da tutti i moduli/materie.
Ogni blueprint importa 'client' da qui invece di crearne uno proprio,
così la ANTHROPIC_API_KEY viene letta una sola volta.
"""
import anthropic
import os

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
