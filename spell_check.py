import re
from textwrap import wrap
from subprocess import Popen, PIPE
import pexpect
import pandas as pd
from tqdm import tqdm
from pathlib import Path


ALL_CHARS = set("0123456789abcdefghijklmnopqrstuvwxyz")
ALL_CHARS.update("ABCDEFGHIJKLMNOPQRSTUVWXYZ .,!?'-")


def split_long(text):
    text = re.sub('- ', '', text)
    text = re.sub(' +', ' ', text).strip()
    lines = wrap(text, 200, break_long_words=False)
    return lines


def tokenize_characters(text):
    text = text.strip()
    text = ''.join(ch if ch in ALL_CHARS else '#' for ch in text)
    text = re.sub(' +', ' ', text).strip()
    tokens = [ch if ch != ' ' else '▁' for ch in text]
    return tokens


def get_tokens(text):
    tokens = tokenize_characters(text)[:1023]
    return ' '.join(tokens)


def get_fairseq_output(line):
    command = ['fairseq-interactive',
               'model7m/',
               '--path', 'model7m/checkpoint_best.pt',
               '--source-lang', 'fr',
               '--target-lang', 'en',
               '--beam', '10']
    p = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True)
    out = p.communicate(line)
    outlines = out[0].split('\n')
    return outlines


def format_output(lines):
    prev_line_no = None
    for line in lines:
        match = re.match(r'^H-(\d+)', line)
        if not match:
            continue
        tokens = line.split('\t')[2].split(' ')
        text = ''.join(tokens)
        line_no = int(match.group(1))
        assert not prev_line_no or line_no == prev_line_no + 1
        prev_line_no = line_no
        text = text.replace('▁', ' ')
        return text


def spell_check(text):
    corrected_lines = []

    if type(text) == 'str':
        lines = split_long(text)

        for line in lines:
            line_toks = get_tokens(line)
            corrected_toks = get_fairseq_output(line_toks)
            out = format_output(corrected_toks)
            corrected_lines.append(out)
    return ' '.join(corrected_lines)


def initialize_spell_check():
    command = ['fairseq-interactive',
               'model7m/',
               '--path', 'model7m/checkpoint_best.pt',
               '--source-lang', 'fr',
               '--target-lang', 'en',
               '--beam', '10']
    command = ' '.join(command)

    p = pexpect.spawn(command, timeout=90, encoding='utf-8')
    p.expect('.*return:')
    print(p.after)
    return p


def spell_check_alt(p, doc):
    lines = split_long(doc)
    corrected_lines = []

    for line in lines:
        p.sendline(get_tokens(line))
        p.expect(r'\d\r\n')
        out = p.before
        out = out.split('\r\n')
        out = format_output(out)
        corrected_lines.append(out)

    return ' '.join(corrected_lines)


if __name__ == '__main__':
    p = initialize_spell_check()
    unrest_texts = pd.read_csv('unrest_texts.csv', index_col=0)
    for article in tqdm(unrest_texts.index.to_list()):
        path = Path('temp', str(article) + '.txt')

        if not path.exists():
            text = unrest_texts.article_text.loc[article]
            new_text = spell_check(text)
            with open(path, 'w') as f:
                f.write(new_text)
