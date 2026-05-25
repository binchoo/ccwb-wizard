"""CFN YAML quick check (handles intrinsic functions)."""
import sys
import yaml


class CFNLoader(yaml.SafeLoader):
    pass


def cfn_constructor(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {f"Fn::{tag_suffix}": loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {f"Fn::{tag_suffix}": loader.construct_sequence(node, deep=True)}
    if isinstance(node, yaml.MappingNode):
        return {f"Fn::{tag_suffix}": loader.construct_mapping(node, deep=True)}
    raise NotImplementedError


CFNLoader.add_multi_constructor("!", cfn_constructor)

for path in sys.argv[1:]:
    src = open(path).read()
    try:
        doc = yaml.load(src, Loader=CFNLoader)
        n_res = len(doc.get("Resources", {}))
        n_out = len(doc.get("Outputs", {}))
        print(f"{path}: OK ({n_res} resources, {n_out} outputs)")
    except yaml.YAMLError as e:
        print(f"{path}: FAIL — {e}")
        sys.exit(1)
