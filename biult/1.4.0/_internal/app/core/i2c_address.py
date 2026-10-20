"""Seven-bit I2C addresses; old decimal ELS values remain readable."""
def parse_address(raw):
    text=str(raw).strip()
    value=int(text,16 if text.lower().startswith('0x') else 10)
    if not 0<=value<=0x7f: raise ValueError('I2C address must be 0x00..0x7F')
    return value
