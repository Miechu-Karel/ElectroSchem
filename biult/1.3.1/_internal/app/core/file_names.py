"""Portable filename suggestions derived from a project title."""
import re


def project_filename(title, extension):
    name=re.sub(r'[<>:"/\\|?*\x00-\x1f]',"_",re.sub(r"\s+"," ",str(title)))
    name=re.sub(r"\s+"," ",name).strip(" .")[:160].rstrip(" .") or "project"
    if name.casefold().endswith("."+extension.casefold()): name=name[:-(len(extension)+1)] or "project"
    if name.split(".")[0].upper() in {"CON","PRN","AUX","NUL",*(f"COM{i}" for i in range(1,10)),*(f"LPT{i}" for i in range(1,10))}:
        name="_"+name
    return name+"."+extension
