# OpenChapters Chapter Repo Conventions

The OpenChapters repo contains the following files and folders:

* matter: this folder contains the frontmatter.tex and postmatter.tex files as well as an eps folder for figures
* src: this folder contains a subfolder for each chapter
    * chapter folder: contains a \<chaptername\>.tex source file, a chaptercitations.bib file, and an eps folder with all chapter figures
* Build: 
    * main.tex: main typesetting file with arara embedded commands. 
    * .sty files: 
        * OpenChapters.sty: main style file
        * mytodonotes.sty: style file for marginal notes etc.
        * arara.sty: additional style commands
    * .ins files:
        * preamble.ins: file with user-defined commands
    * .ist files:
        * StyleInd.ist: instructions for formatting of the index
    * .bib files:
        * OpenChapters.bib: this file is created by arara as part of the typesetting preparations by concatenating all chapter bib files    
    * ImageFolder: during typesetting, all figures for the selected chapters are copied here by an arara script.
    * matter and src folders: symbolic links to the actual folders described above [this is probably not the best way to do this]
* EPUBBuild: ignore folder for now
* HTMLBuild: ignore folder for now
* README.MD: brief description
* ChapterTitles.txt: currently unused; should contain a list of chapters that need to be typeset. File should be created by web engine, then python script parses this file to generate a custom main.tex file.

General note: the name of the Build folder should probably be set for each individual book typesetting request.  During testing of the typesetting code, this was the easier way to structure this.  

Several of the arara commands embedded in the main.tex file call functions that currently are defined in the top .bashrc file. This will all need to be replaed with calls to python scripts to facilitate maintaining the code base. 



