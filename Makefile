OUTDIR:= build
OUTFILENAME:= package.zip

define SYSHACK
#!/usr/bin/env python
import os
import sys

# add our location to python path
sys.path.append(os.path.dirname(__file__))
endef

export SYSHACK

$(OUTFILENAME): $(OUTDIR)
	@echo "cleanup shipped dependencies"
	
	# remove the bin dir
	rm -rf $(OUTDIR)/plugins/bin

	# remove cache
	find $(OUTDIR) -iname __pycache__ -type d -exec rm -rf {} \+
	find $(OUTDIR) -iname *.dist-info -type d -exec rm -rf {} \+

	@echo zip build dir
	cd $(OUTDIR) && zip -r $@ *
	cp $(OUTDIR)/$@ $@

$(OUTDIR):
	mkdir -p $@

	mkdir -p $@/{plugins,resources}
	cp package/metadata_template.json $@/metadata.json

	# bundle all script dependencies to single python file using stickytape 
	stickytape --output-file $@/plugins/__init__.py easyEdaWizard.py	

	# add sys path hack to preamble
	echo "$$SYSHACK" | cat - $@/plugins/__init__.py > $@/temp.py
	mv $@/temp.py  $@/plugins/__init__.py 

	# now also download easyeda2kicad to the plugins directory
	pip install -t $(OUTDIR)/plugins/ easyeda2kicad

.PHONY: clean

clean: 
	$(RM) -rf $(OUTDIR) package.zip