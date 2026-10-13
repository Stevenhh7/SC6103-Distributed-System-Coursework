"""Render Markdown with linked contents and immutable screenshot viewports."""
import argparse
from pathlib import Path
import re
from urllib.parse import parse_qs
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate,Flowable,Frame,NextPageTemplate,
    PageBreak,PageTemplate,Paragraph,Spacer,Table,TableStyle,KeepTogether)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT=Path(__file__).resolve().parents[1]
NAVY=colors.HexColor('#16334d');BLUE=colors.HexColor('#365f7e');MARGIN=48

class Screenshot(Flowable):
    """Frame the original image on the PDF canvas without changing its bytes."""
    def __init__(self,path,view=None,maxheight=300):
        super().__init__();self.path=str(path);self.reader=ImageReader(self.path)
        self.iw,self.ih=self.reader.getSize();self.view=view or (0,0,self.iw,self.ih)
        x,y,w,h=self.view
        if min(x,y)<0 or min(w,h)<=0 or x+w>self.iw or y+h>self.ih:
            raise ValueError(f'Invalid screenshot viewport: {self.view}')
        self.maxheight=maxheight;self.hAlign='CENTER';self.spaceBefore=4;self.spaceAfter=7
    def wrap(self,availWidth,availHeight):
        self.scale=min(availWidth/self.view[2],self.maxheight/self.view[3])
        self.width=self.view[2]*self.scale;self.height=self.view[3]*self.scale
        return self.width,self.height
    def draw(self):
        x,y,w,h=self.view;c=self.canv;c.saveState()
        boundary=c.beginPath();boundary.rect(0,0,self.width,self.height)
        c.clipPath(boundary,stroke=0,fill=0)
        c.drawImage(self.reader,-x*self.scale,-(self.ih-y-h)*self.scale,
                    width=self.iw*self.scale,height=self.ih*self.scale,mask='auto')
        c.restoreState();c.setStrokeColor(colors.HexColor('#ccd5dd'));c.setLineWidth(.35)
        c.rect(0,0,self.width,self.height,stroke=1,fill=0)

class ReportDoc(BaseDocTemplate):
    def afterFlowable(self,flowable):
        if isinstance(flowable,Paragraph) and flowable.style.name=='Section':
            title=flowable.getPlainText()
            if title=='Contents':return
            key='section-'+re.sub(r'[^a-zA-Z0-9]+','-',title)
            self.canv.bookmarkPage(key);self.canv.addOutlineEntry(title,key,0,False)
            self.notify('TOCEntry',(0,title,self.page,key))

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--font',type=Path)
    p.add_argument('--source',type=Path,default=ROOT/'report/项目报告.md')
    p.add_argument('--output',type=Path,default=ROOT/'output/pdf/SC6103_Project_Report.pdf')
    p.add_argument('--date')
    args=p.parse_args(argv);source=args.source.resolve()
    lines=source.read_text(encoding='utf-8').splitlines()
    date_match=re.search(r'Course Project Report \| ([^|]+) \|','\n'.join(lines[:15]))
    date=args.date or (date_match.group(1).strip() if date_match else '12 October 2026')
    unicode_font='STSong-Light'
    for candidate in [args.font,Path('/System/Library/Fonts/Supplemental/Arial Unicode.ttf'),Path('C:/Windows/Fonts/msyh.ttc')]:
        if candidate and candidate.is_file():
            try:
                pdfmetrics.registerFont(TTFont('ReportUnicode',str(candidate),subfontIndex=0))
                unicode_font='ReportUnicode';break
            except Exception:
                if candidate==args.font:raise
    if unicode_font=='STSong-Light':pdfmetrics.registerFont(UnicodeCIDFont(unicode_font))
    faces={'Helvetica':'Helvetica','Helvetica-Bold':'Helvetica-Bold','Courier':'Courier'}
    font_sets=[(Path('C:/Windows/Fonts/arial.ttf'),Path('C:/Windows/Fonts/arialbd.ttf'),Path('C:/Windows/Fonts/consola.ttf')),
               (Path('/System/Library/Fonts/Supplemental/Arial.ttf'),Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf'),Path('/System/Library/Fonts/Supplemental/Courier New.ttf'))]
    for regular,bold,mono in font_sets:
        if all(f.is_file() for f in (regular,bold,mono)):
            for name,file in [('ReportSans',regular),('ReportSans-Bold',bold),('ReportMono',mono)]:
                pdfmetrics.registerFont(TTFont(name,str(file)))
            pdfmetrics.registerFontFamily('ReportSans',normal='ReportSans',bold='ReportSans-Bold',italic='ReportSans',boldItalic='ReportSans-Bold')
            faces={'Helvetica':'ReportSans','Helvetica-Bold':'ReportSans-Bold','Courier':'ReportMono'}
            break
    style_specs={
      'Body':dict(fontName='Helvetica',fontSize=10.1,leading=14.3,spaceAfter=8.5),
      'Landscape':dict(fontName='Helvetica',fontSize=9.4,leading=12.7,spaceAfter=8),
      'Title':dict(fontName='Helvetica-Bold',fontSize=27,leading=33,textColor=NAVY,spaceBefore=29,spaceAfter=22),
      'Section':dict(fontName='Helvetica-Bold',fontSize=17,leading=22,textColor=NAVY,spaceAfter=14,keepWithNext=True),
      'Sub':dict(fontName='Helvetica-Bold',fontSize=11.6,leading=16,textColor=BLUE,spaceBefore=8,spaceAfter=9,keepWithNext=True),
      'Caption':dict(fontName='Helvetica',fontSize=8.7,leading=11.5,textColor=BLUE,spaceAfter=8),
      'Cell':dict(fontName='Helvetica',fontSize=8.5,leading=11.3),
      'HeaderCell':dict(fontName='Helvetica-Bold',fontSize=8.5,leading=11.3,textColor=NAVY),
      'Code':dict(fontName='Courier',fontSize=8.2,leading=12,backColor=colors.HexColor('#eef3f7'),
                  borderPadding=7,spaceBefore=5,spaceAfter=12)}
    for spec in style_specs.values():spec['fontName']=faces[spec['fontName']]
    styles={k:ParagraphStyle(k,textColor=colors.HexColor('#253342'),splitLongWords=1,**{x:y for x,y in v.items() if x!='textColor'}) for k,v in style_specs.items()}
    for key,spec in style_specs.items():
        if 'textColor' in spec:styles[key].textColor=spec['textColor']
    def markup(s):
        s=escape(s);s=re.sub(r'\*\*(.*?)\*\*',r'<b>\1</b>',s)
        s=re.sub(r'`(.*?)`',lambda m:f'<font name="{faces["Courier"]}" size="8.6">'+m.group(1)+'</font>',s)
        return re.sub(r'([^\x00-\x7f]+)',lambda m:f'<font name="{unicode_font}">{m.group(1)}</font>',s)
    def para(s,style='Body'):return Paragraph(markup(s),styles[style])
    def page(c,doc):
        w,h=c._pagesize;c.saveState();c.setStrokeColor(colors.HexColor('#c6d2dc'));c.setLineWidth(.6)
        c.line(MARGIN,h-32,w-MARGIN,h-32);c.setFont(faces['Helvetica'],8);c.setFillColor(BLUE)
        c.drawString(MARGIN,h-24,'SC6103  |  DISTRIBUTED FLIGHT INFORMATION SYSTEM')
        c.line(MARGIN,42,w-MARGIN,42);c.drawString(MARGIN,29,'Course project report  |  '+date)
        c.drawRightString(w-MARGIN,29,str(doc.page));c.restoreState()
    output=args.output.resolve();output.parent.mkdir(parents=True,exist_ok=True)
    doc=ReportDoc(str(output),pagesize=A4,leftMargin=MARGIN,rightMargin=MARGIN,topMargin=50,bottomMargin=54,
                  title='SC6103 Distributed Flight Information System',author='Zhang Zhiyin; Peng Jinyu; Ji Chengyu',
                  subject='Java/Python UDP; invocation semantics and observed experiments')
    for name,size in [('portrait',A4),('landscape',landscape(A4))]:
        frame=Frame(MARGIN,54,size[0]-2*MARGIN,size[1]-104,leftPadding=0,rightPadding=0,
                    topPadding=0,bottomPadding=0,id=name+'-frame')
        doc.addPageTemplates(PageTemplate(id=name,frames=[frame],onPage=page,pagesize=size))
    story=[];orientation='portrait';i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line in ('<!-- portrait-page -->','<!-- landscape-page -->'):
            orientation='portrait' if 'portrait' in line else 'landscape'
            story.extend([NextPageTemplate(orientation),PageBreak()]);i+=1;continue
        if line=='<!-- contents -->':
            toc=TableOfContents();toc.dotsMinLevel=0;toc.levelStyles=[ParagraphStyle('TOC',fontName=faces['Helvetica'],fontSize=11,
                leading=19,textColor=NAVY,spaceBefore=11)]
            story.append(toc);i+=1;continue
        if line.startswith('# '):story.append(para(line[2:],'Title'));i+=1;continue
        if line.startswith('## '):story.append(para(line[3:],'Section'));i+=1;continue
        if line.startswith('### '):story.append(para(line[4:],'Sub'));i+=1;continue
        matched=re.fullmatch(r'!\[(.*?)\]\((.*?)\)',line)
        if matched:
            caption,target=matched.groups();pathpart,_,fragment=target.partition('#')
            path=(source.parent/pathpart).resolve()
            if not path.is_relative_to(source.parent) or not path.is_file():raise ValueError(f'Invalid asset: {target}')
            settings=parse_qs(fragment)
            view=tuple(map(float,settings['view'][0].split(','))) if 'view' in settings else None
            shot=Screenshot(path,view,float(settings.get('maxh',['300'])[0]))
            story.append(KeepTogether([shot,para(caption,'Caption')]))
            i+=1;continue
        if line.startswith('```'):
            i+=1;block=[]
            while i<len(lines) and not lines[i].startswith('```'):block.append(lines[i]);i+=1
            story.append(Paragraph('<br/>'.join(escape(x) for x in block),styles['Code']));i+=1;continue
        if line.startswith('|'):
            raw=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',x) for x in cells):raw.append(cells)
                i+=1
            n=len(raw[0]);assert all(len(row)==n for row in raw)
            width=(A4[0] if orientation=='portrait' else landscape(A4)[0])-2*MARGIN;weights=[1/n]*n
            if raw[0][0]=='Group member':weights=[.24,.56,.20]
            elif raw[0][0]=='Header field':weights=[.24,.10,.66]
            elif raw[0][0]=='Operation' and n==3:weights=[.30,.33,.37]
            elif raw[0][0]=='Operation' and n==5:weights=[.23,.10,.13,.29,.25]
            elif n==2:weights=[.77,.23]
            elif raw[0][0]=='Case':weights=[.30,.35,.35]
            elif raw[0][0]=='Role':weights=[.26,.22,.52]
            elif raw[0][0]=='Experiment':weights=[.28,.29,.43]
            cells=[[para(v,'HeaderCell' if rownum==0 else 'Cell') for v in row] for rownum,row in enumerate(raw)]
            table=Table(cells,colWidths=[width*w for w in weights],repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dfeaf3')),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f7f9')]),
                ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),
                ('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),
                ('BOTTOMPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#9bb1c1'))]))
            story.extend([table,Spacer(1,12)]);continue
        if line.startswith('<!--'):i+=1;continue
        if re.match(r'^\d+\. ',line):story.append(para(line,'Landscape' if orientation=='landscape' else 'Body'));i+=1;continue
        block=[line];i+=1
        while i<len(lines) and lines[i].strip() and not lines[i].strip().startswith(('#','|','```','![','<!--')):
            block.append(lines[i].strip());i+=1
        story.append(para(' '.join(block),'Landscape' if orientation=='landscape' else 'Body'))
    doc.multiBuild(story);print(output);return 0

if __name__=='__main__':raise SystemExit(main())
