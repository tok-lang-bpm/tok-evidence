import csv
import json
import os

import datasets


# Find for instance the citation on arxiv or on the dataset repo/website
_CITATION = """\
@inproceedings{DBLP:conf/bpm/BellanADGP22,
  author       = {Patrizio Bellan and
                  Han van der Aa and
                  Mauro Dragoni and
                  Chiara Ghidini and
                  Simone Paolo Ponzetto},
  editor       = {Cristina Cabanillas and
                  Niels Frederik Garmann{-}Johnsen and
                  Agnes Koschmider},
  title        = {{PET:} An Annotated Dataset for Process Extraction from Natural Language
                  Text Tasks},
  booktitle    = {Business Process Management Workshops - {BPM} 2022 International Workshops,
                  M{\"{u}}nster, Germany, September 11-16, 2022, Revised Selected
                  Papers},
  series       = {Lecture Notes in Business Information Processing},
  volume       = {460},
  pages        = {315--321},
  publisher    = {Springer},
  year         = {2022},
  url          = {https://doi.org/10.1007/978-3-031-25383-6\_23},
  doi          = {10.1007/978-3-031-25383-6\_23},
  timestamp    = {Tue, 14 Feb 2023 09:47:10 +0100},
  biburl       = {https://dblp.org/rec/conf/bpm/BellanADGP22.bib},
  bibsource    = {dblp computer science bibliography, https://dblp.org}
}
@inproceedings{DBLP:conf/aiia/BellanGDPA22,
  author       = {Patrizio Bellan and
                  Chiara Ghidini and
                  Mauro Dragoni and
                  Simone Paolo Ponzetto and
                  Han van der Aa},
  editor       = {Debora Nozza and
                  Lucia C. Passaro and
                  Marco Polignano},
  title        = {Process Extraction from Natural Language Text: the {PET} Dataset and
                  Annotation Guidelines},
  booktitle    = {Proceedings of the Sixth Workshop on Natural Language for Artificial
                  Intelligence {(NL4AI} 2022) co-located with 21th International Conference
                  of the Italian Association for Artificial Intelligence (AI*IA 2022),
                  Udine, November 30th, 2022},
  series       = {{CEUR} Workshop Proceedings},
  volume       = {3287},
  pages        = {177--191},
  publisher    = {CEUR-WS.org},
  year         = {2022},
  url          = {https://ceur-ws.org/Vol-3287/paper18.pdf},
  timestamp    = {Fri, 10 Mar 2023 16:23:01 +0100},
  biburl       = {https://dblp.org/rec/conf/aiia/BellanGDPA22.bib},
  bibsource    = {dblp computer science bibliography, https://dblp.org}
}

"""

# You can copy an official description
_DESCRIPTION = """\
Abstract. Although there is a long tradition of work in NLP on extracting entities and relations from text, to date there exists little work on the acquisition of business processes from unstructured data such as textual corpora of process descriptions. With this work we aim at filling this gap and establishing the first steps towards bridging data-driven information extraction methodologies from Natural Language Processing and the model-based formalization that is aimed from Business Process Management. For this, we develop the first corpus of business process descriptions annotated with activities, gateways, actors and flow information. We present our new resource, including a detailed overview of the annotation schema and guidelines, as well as a variety of baselines to benchmark the difficulty and challenges of business process extraction from text.
"""

_HOMEPAGE = "https://pdi.fbk.eu/pet-dataset/"

_LICENSE = "MIT"

_URL_11 = "https://raw.githubusercontent.com/patriziobellan86/PETv1.1/master/"
_URL_10 = "https://pdi.fbk.eu/pet/PETHuggingFace/"
_TEST_FILE_11 = "PETv1.1-entities.jsonl"
_TEST_FILE_10 = "test.json"
_TEST_FILE_RELATIONS_11 = "PETv1.1-relations.json"
_TEST_FILE_RELATIONS_10 = 'PETrelations.json'

_NER = 'token-classification'
_NER_11 = 'token-classification-v1.1'
_RELATIONS_EXTRACTION = 'relations-extraction'
_RELATIONS_EXTRACTION_11 = 'relations-extraction-v1.1'

_NER_TAGS = [ "O",
            "B-Actor",
            "I-Actor",
            "B-Activity",
            "I-Activity",
            "B-Activity Data",
            "I-Activity Data",
            "B-Further Specification",
            "I-Further Specification",
            "B-XOR Gateway",
            "I-XOR Gateway",
            "B-Condition Specification",
            "I-Condition Specification",
            "B-AND Gateway",
            "I-AND Gateway"]

_STR_PET = """\n
 _______ _     _ _______       _____  _______ _______      ______  _______ _______ _______ _______ _______ _______
    |    |_____| |______      |_____] |______    |         |     \ |_____|    |    |_____| |______ |______    |   
    |    |     | |______      |       |______    |         |_____/ |     |    |    |     | ______| |______    |   
                                                                                                                  
Discover more at: [https://pdi.fbk.eu/pet-dataset/]
"""


class PETConfig(datasets.BuilderConfig):
    """The PET Dataset."""

    def __init__(self, **kwargs):
        """BuilderConfig for PET.
        Args:
          **kwargs: keyword arguments forwarded to super.
        """
        super(PETConfig, self).__init__(**kwargs)

class PET(datasets.GeneratorBasedBuilder):
    """PET DATASET."""

    features_ner = {
            "document name": datasets.Value("string"),
            "sentence-ID": datasets.Value("int8"),
            "tokens": datasets.Sequence(datasets.Value("string")),
            "ner-tags": datasets.Sequence(datasets.features.ClassLabel(names=_NER_TAGS)),
        }

    features_relations = datasets.Sequence(
        datasets.Features(

        {
            'source-head-sentence-ID': datasets.Value("int8"),
            'source-head-word-ID': datasets.Value("int8"),
            'relation-type': datasets.Value("string"),
            'target-head-sentence-ID': datasets.Value("int8"),
            'target-head-word-ID' : datasets.Value("int8"),
        }
    ))
    BUILDER_CONFIGS = [ PETConfig(
                            name=_NER,
                            version=datasets.Version("1.0.1"),
                            description="The PET Dataset for Token Classification"
                            ),
                        PETConfig(
                            name=_RELATIONS_EXTRACTION,
                            version=datasets.Version("1.0.1"),
                            description="The PET Dataset for Relation Extraction"
                            ),
                        PETConfig(
                            name=_NER_11,
                            version=datasets.Version("1.1.0"),
                            description="The PET Dataset for Token Classification"
                            ),
                        PETConfig(
                            name=_RELATIONS_EXTRACTION_11,
                            version=datasets.Version("1.1.0"),
                            description="The PET Dataset for Relation Extraction"
                            ),
                        ]

    DEFAULT_CONFIG_NAME = _RELATIONS_EXTRACTION

    def _info(self):
        print(_STR_PET)
        if self.config.name == _NER:
            features = datasets.Features(self.features_ner)
        else:
            features = datasets.Features(
                {
                "document name": datasets.Value("string"),
                'tokens':datasets.Sequence(datasets.Value("string")),
                'tokens-IDs':datasets.Sequence(datasets.Value("int8")),
                'ner_tags': datasets.Sequence(datasets.Value("string")),
                'sentence-IDs':datasets.Sequence(datasets.Value("int8")),
                "relations": self.features_relations
                }
            )
        # print(features)
        return datasets.DatasetInfo(
            description=_DESCRIPTION,
            features=datasets.Features(features),
            homepage=_HOMEPAGE,
            license=_LICENSE,
            citation=_CITATION,
        )

    def _split_generators(self, dl_manager):
        print(f"{self.config.version}")
        if self.config.name == _NER:
            urls_to_download = {
                    "test": f"{_URL_10}{_TEST_FILE_10}",
                }
            downloaded_files = dl_manager.download_and_extract(urls_to_download)
            return [datasets.SplitGenerator(
                    name=datasets.Split.TEST,
                    # These kwargs will be passed to _generate_examples
                    gen_kwargs={
                            "filepath": downloaded_files["test"],
                            "split":    "test"
                    },
            )]
        elif self.config.name == _NER_11:
            urls_to_download = {
                "test": f"{_URL_11}{_TEST_FILE_11}",
            }

            downloaded_files = dl_manager.download_and_extract(urls_to_download)
            return [datasets.SplitGenerator(
                        name=datasets.Split.TEST,
                        # These kwargs will be passed to _generate_examples
                        gen_kwargs={
                            "filepath": downloaded_files["test"],
                            "split": "test"
                        },
                    )]

        elif self.config.name == _RELATIONS_EXTRACTION:
            urls_to_download = {
                    "test": f"{_URL_10}{_TEST_FILE_RELATIONS_10}",
                }
            downloaded_files = dl_manager.download_and_extract(urls_to_download)
            return [datasets.SplitGenerator(
                    name=datasets.Split.TEST,
                    # These kwargs will be passed to _generate_examples
                    gen_kwargs={
                            "filepath": downloaded_files["test"],
                            "split":    "test"
                            },
                    )]

        else:
            urls_to_download = {
                "test": f"{_URL_11}{_TEST_FILE_RELATIONS_11}",
            }
            downloaded_files = dl_manager.download_and_extract(urls_to_download)
            return [datasets.SplitGenerator(
                name=datasets.Split.TEST,
                # These kwargs will be passed to _generate_examples
                gen_kwargs={
                    "filepath": downloaded_files["test"],
                    "split": "test"
                    },
                )]

    def _generate_examples(self, filepath, split):
        if self.config.name == _NER:
            with open(filepath, encoding="utf-8", mode='r') as f:
                for key, row in enumerate(f):
                    row = json.loads(row)
                    yield key, {
                                "document name": row["document name"],
                                "sentence-ID": row["sentence-ID"],
                                "tokens": row["tokens"],
                                "ner-tags": row["ner-tags"]
                                }
        else:
            with open(filepath, encoding="utf-8", mode='r') as f:
                for key, row in enumerate(json.load(f)):
                    yield key, {"document name": row["document name"],
                                'tokens': row["tokens"],
                                'tokens-IDs': row["tokens-IDs"],
                                'ner_tags': row["ner_tags"],
                                'sentence-IDs': row["sentence-IDs"],

                                "relations": row["relations"]
                                }
