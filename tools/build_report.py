"""Render the integrated Markdown report. Optional dependency: reportlab.

Usage: python tools/build_report.py [--font /path/to/a/Unicode.ttf]
Program/server execution does not require this document-only dependency.
"""
import argparse
from pathlib import Path
import re
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--font', type=Path)
a = p.parse_args()
font = a.font or Path('/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
if font.is_file():
    pdfmetrics.registerFont(TTFont('ReportUnicode', str(font)))
else:
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
UNICODE = 'ReportUnicode' if font.is_file() else 'STSong-Light'
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodyReport', fontName='Helvetica', fontSize=10, leading=14.6, spaceAfter=9))
styles.add(ParagraphStyle(name='TableReport', fontName='Helvetica', fontSize=8.6, leading=11.5))
styles.add(ParagraphStyle(name='CodeReport', fontName='Courier', fontSize=8.4, leading=12, spaceAfter=10, backColor=colors.HexColor('#f0f4f8'), borderPadding=8))
styles['Title'].fontSize=25; styles['Title'].leading=31; styles['Title'].textColor=colors.HexColor('#173653')
styles['Heading2'].fontSize=16; styles['Heading2'].leading=21; styles['Heading2'].spaceAfter=15; styles['Heading2'].textColor=colors.HexColor('#173653')

def markup(s):
    s=escape(s)
    s=re.sub(r'\*\*(.*?)\*\*',r'<b>\1</b>',s)
    s=re.sub(r'`(.*?)`',r'<font name="Courier">\1</font>',s)
    # Embedded Unicode references stay readable without altering the English face.
    return re.sub(r'([^\x00-\x7f]+)',lambda m:'<font name="'+UNICODE+'">'+m.group(1)+'</font>',s)

def para(s,style='BodyReport'):return Paragraph(markup(s),styles[style])

lines=(ROOT/'report/项目报告.md').read_text(encoding='utf-8').splitlines()
story=[];i=0
while i<len(lines):
    line=lines[i].strip()
    if not line:i+=1;continue
    if line.startswith('# '):
        story.extend([Spacer(1,45),para(line[2:],'Title'),Spacer(1,20)]);i+=1;continue
    if line.startswith('## '):
        story.extend([PageBreak(),para(line[3:],'Heading2')]);i+=1;continue
    if line.startswith('```'):
        i+=1;block=[]
        while i<len(lines) and not lines[i].startswith('```'):block.append(lines[i]);i+=1
        story.append(Paragraph('<br/>'.join(escape(x) for x in block),styles['CodeReport']));i+=1;continue
    if line.startswith('|'):
        rows=[]
        while i<len(lines) and lines[i].strip().startswith('|'):
            cells=[v.strip() for v in lines[i].strip().strip('|').split('|')]
            if not all(re.fullmatch(r':?-+:?',v) for v in cells):rows.append([para(c,'TableReport') for c in cells])
            i+=1
        n=len(rows[0]);width=483
        # Favour description and observation columns.
        weights=[.32,.68] if n==2 else [.28,.36,.36]
        if 'Header field' in line:weights=[.25,.12,.63]
        if 'Verification suite' in line:weights=[.72,.28]
        table=Table(rows,colWidths=[width*w for w in weights],repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dfeaf4')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#8fa8bd')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f7fa')])]))
        story.extend([table,Spacer(1,14)]);continue
    if re.match(r'^\d+\. ',line):
        story.append(para(line));i+=1;continue
    block=[line];i+=1
    while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','```')):
        block.append(lines[i].strip());i+=1
    story.append(para(' '.join(block)))

out=ROOT/'output/pdf/SC6103_Project_Report.pdf';out.parent.mkdir(parents=True,exist_ok=True)
def page(c,doc):
    c.saveState();c.setStrokeColor(colors.HexColor('#ccd8e3'));c.line(56,45,539,45)
    c.setFont('Helvetica',8);c.setFillColor(colors.HexColor('#526779'))
    c.drawString(56,32,'SC6103 | Team review copy | 10 October 2026');c.drawRightString(539,32,str(doc.page));c.restoreState()
doc=SimpleDocTemplate(str(out),pagesize=A4,rightMargin=56,leftMargin=56,topMargin=52,bottomMargin=60,title='SC6103 Distributed Flight Information System',author='Zhang Zhiyin; Peng Jinyu; Ji Chengyu')
doc.build(story,onFirstPage=page,onLaterPages=page)
print(out)
