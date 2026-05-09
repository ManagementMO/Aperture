# Workbench Boundary

Workbench stores or processes large outputs outside model context. Aperture
decides what compact version of those outputs the model sees.

They can work together: Workbench or an object store preserves the full payload,
while Aperture returns a compressed envelope with a raw reference for later
retrieval.

