def mock_transcript_for_turn(turn_index: int) -> str:
    samples = [
        "I came because the light drew me in; I've been running on habit for months.",
        "I'm not sure. Part of me wanted stillness, part wanted to be seen.",
        "If I'm honest, I'm afraid of what happens when I stop moving.",
    ]
    return samples[turn_index % len(samples)]
