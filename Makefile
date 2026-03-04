scrape:
	python scraper/run.py

consolidate:
	python -m src.pipeline.consolidate

features:
	python -m src.pipeline.features

pipeline: consolidate features

test:
	pytest tests/

archive:
	xcopy data\ data\archive\%date%\ /E /I