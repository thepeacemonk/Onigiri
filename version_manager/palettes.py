"""Self-contained selector palettes, retained when Current is downgraded.

Bento's colors mirror core.config.DEFAULTS['colors']; choosing a release only
previews this dialog's palette and never changes any saved Onigiri theme.
"""
PALETTES = {
    "2.0-Bento": {
        "light": dict(background="#ffffff", field="#ffffff", ink="#202124", muted="#63666c",
                      line="#e3e4e7", accent="#33AEBF", accent_hover="#42BBCB", on_accent="#123034",
                      hover="#f7f7f6", switch_off="#858B94", knob="#FFFFFF"),
        "dark": dict(background="#171717", field="#202020", ink="#f1f2f4", muted="#b0b3ba",
                     line="#45464b", accent="#33AEBF", accent_hover="#42BBCB", on_accent="#123034",
                     hover="#1d1d1d", switch_off="#62666F", knob="#FFFFFF"),
    },
    "1.0-Sake-Nigiri": {
        "light": dict(background="#FBF7F3", field="#FFFCF9", ink="#413530", muted="#75645B",
                      line="#E6DAD1", accent="#99634F", accent_hover="#88533F", on_accent="#FFFFFF",
                      hover="#F2E9E1", switch_off="#96847B", knob="#FFFFFF"),
        "dark": dict(background="#26201D", field="#302722", ink="#F0E7E1", muted="#C4B1A7",
                     line="#59483E", accent="#CEAA97", accent_hover="#DEBCAB", on_accent="#33241D",
                     hover="#3A2E27", switch_off="#796459", knob="#FFFFFF"),
    },
    "0.9-legacy": {
        "light": dict(background="#F6F5F9", field="#FDFBFF", ink="#353342", muted="#6E687D",
                      line="#DFDAE8", accent="#6E668C", accent_hover="#5E577B", on_accent="#FFFFFF",
                      hover="#EEEBF4", switch_off="#8E879F", knob="#FFFFFF"),
        "dark": dict(background="#24232C", field="#2F2D39", ink="#ECEAF2", muted="#BBB5CC",
                     line="#514C61", accent="#B4AACE", accent_hover="#C6BDDE", on_accent="#292437",
                     hover="#393543", switch_off="#716983", knob="#FFFFFF"),
    },
}


def palette_for(version, dark=False):
    return dict(PALETTES[version]["dark" if dark else "light"])
