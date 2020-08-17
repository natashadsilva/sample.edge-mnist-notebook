# sample.edge-mnist-notebook

This sample demonstrates the use of a Streams Python Notebook, and Edge Analytics in
Cloud Pak for Data, to recognize digit images using a simple scikit-learn ML
model trained with the standard MNIST digit dataset.

The Micro-Edge job communicates to a job running in the Metro-Edge using IBM
Eventstreams topics, and a Notebook running at the Metro-Edge can be used to see,
in real-time, statistics on the Micro-Edge digit predictions, as well as seeing
uncertain digit predictions, which could be used to re-train the prediction model
to improve accuracy, etc.

