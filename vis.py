#!/usr/bin/env python3

import argparse
from dataclasses import dataclass
from rdflib import Graph, URIRef, OWL, RDFS, RDF, SKOS, term
from typing import Tuple, Dict, Generator, List, Set


Node = term.Node

store = Graph()

prefixes = {
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "sh": "http://www.w3.org/ns/shacl#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}


@dataclass
class GistClass:
    """
    This is a data class for default gist class
    """

    name = URIRef(prefixes["gist"] + "name")
    hasDirectPart = URIRef(prefixes["gist"] + "hasDirectPart")


GIST = GistClass()


def node_generator():
    """
    a generator function to iterate through the alphabet.
    TODO: the function only goes through the 26 letters of the alphabet (upper case and
    lower case) This should be improved to add numeric values as well.
    I don't think this will be too much of a problem: 26 nodes is probably too much data
    to show on a screent
    """
    alphabet = [*"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"]
    for char in alphabet:
        yield char


class NodeStructure:
    """
    Class to keep track of which nodes have been called and associated uris.
    """

    def __init__(self):
        """
        initializing the class with a dictionary and a generator function
        """
        self.dictionary = {}
        self.nodes = node_generator()

    def _genfunc(self):
        """
        this is a protected function to iterate through the node references
        """
        return next(self.nodes)

    def get_node(self, uri: str) -> str:
        """
        if the uri has not been in the dictionary create a new item,
        this creates a special form that is in the form `A(ex:Class)`
        """
        try:
            return self.dictionary[uri]
        except KeyError:
            node = self._genfunc()
            self.dictionary[uri] = node
            name = format_values(str(uri))
            return f"{node}({name})"


def format_values(value: str) -> str:
    """
    Take a uri string and format it to a shorter string.
    Based on the prefixes stored in the prefixes variable.
    """
    for prefix, namespace in prefixes.items():
        if value.startswith(namespace):
            _, local_name = value.split(namespace, maxsplit=2)
            return f"{prefix}:{local_name}"
    return value


def expand_prefix_uri(value: str) -> str:
    """
    take a prefixed form for a uri and expand it to a form
    usable for the URI
    """
    prefix, local_name = value.split(":", maxsplit=1)
    if prefix == "http" or prefix == "https":
        return value
    namespace = prefixes[prefix]
    if not namespace:
        return value
    return f"{namespace}{local_name}"


def find_label(term: Node) -> str:
    """
    Find the best label for a given URI.
    First, skos:prefLabel
    Second, rdfs:label
    Third, gist:name
    Else, return a formated value for the URI
    """
    label = list(store.objects(subject=term, predicate=SKOS.prefLabel))
    if len(label) == 1:
        return str(label.pop())
    label = list(store.objects(subject=term, predicate=RDFS.label))
    if len(label) == 1:
        return str(label.pop())
    label = list(store.objects(subject=term, predicate=GIST.name))
    if len(label) == 1:
        return str(label.pop())
    return format_values(str(term))


def array2list(term: Node, ag: list):
    """
    Turn a RDF List into a python list
    """
    first = list(store.objects(subject=term, predicate=RDF.first)).pop()
    rest = list(store.objects(subject=term, predicate=RDF.rest)).pop()
    ag.append(first)
    if rest == RDF.nil:
        return ag
    return array2list(rest, ag)


def parse_some_values(
    some_values: List[Node],
    prop: Node,
    aggregator: list,
    display_subject: Node,
    visited_nodes: set,
):
    """
    Parse the owl:someValues predicate
    owl:someValues can be either a list or a single value, this handles both cases
    """
    value = some_values.pop()
    # print(prop, value)
    union = list(store.objects(subject=value, predicate=OWL.unionOf))
    if len(union) == 0:
        aggregator.append((display_subject, prop, value))
        return graph_traversal(value, aggregator, value, visited_nodes)
    elif len(union) == 1:
        for uni in array2list(union[0], []):
            aggregator.append((display_subject, prop, uni))
            aggregator, visited_nodes = graph_traversal(
                uni, aggregator, uni, visited_nodes
            )
        return (aggregator, visited_nodes)
    else:
        return (aggregator, visited_nodes)


def parse_owl_restrictions(
    subject: Node, aggregator: list, display_subject: Node, visited_nodes: set
):
    """
    The subject argument is the subject of an owl:Restriction, and this provides
    links to other objects through that restriction
    """
    # find the properties for the owl restriction
    prop = list(store.objects(subject=subject, predicate=OWL.onProperty)).pop()
    # if the restriction is a datatype property just pass buy it
    # TODO: datatype properties could be included in a class object
    # for now we are removing these
    if (prop, RDF.type, OWL.DatatypeProperty) in store:
        return (aggregator, visited_nodes)
    class_objects = list(store.objects(subject=subject, predicate=OWL.onClass))
    some_values = list(store.objects(subject=subject, predicate=OWL.someValuesFrom))
    all_values = list(store.objects(subject=subject, predicate=OWL.allValuesFrom))
    has_value = list(store.objects(subject=subject, predicate=OWL.hasValue))
    # if the restriction is a class object iterate into the class object
    if len(class_objects) == 1:
        class_object = class_objects.pop()
        aggregator.append((display_subject, prop, class_object))
        aggregator, visited_nodes = graph_traversal(
            class_object, aggregator, class_object, visited_nodes
        )
    # if the restriction has some values, iterate into the list of these values
    elif len(some_values) == 1:
        # if all values, iterate into this value
        aggregator, visited_nodes = parse_some_values(
            some_values, prop, aggregator, display_subject, visited_nodes
        )
    elif len(all_values) == 1:
        value = all_values.pop()
        aggregator.append((display_subject, prop, value))
        aggregator, visited_nodes = graph_traversal(
            value, aggregator, value, visited_nodes
        )
    elif len(has_value) == 1:
        value = has_value.pop()
        aggregator.append((display_subject, prop, value))
        aggregator, visited_nodes = graph_traversal(
            value, aggregator, value, visited_nodes
        )
    # currently we aren't doing anything for cardinality
    elif (subject, OWL.minCardinality, None) in store:
        return (aggregator, visited_nodes)
    else:
        print(f"Error in Traversing Graph at {subject}")
        for s, p, o in store.triples((subject, None, None)):
            print(s, p, o)
    return (aggregator, visited_nodes)


def graph_traversal(
    term: Node, aggregator: List[Node], display_subject: Node, visited_nodes: Set[Node]
) -> Tuple[list, set]:
    """
    A recursive function to iterate through an owl definition to find restrictions on
    and return a list of tuples that have the subject, predicate, and objects for how
    classes relate to other classes
    returns a list of tuples and a set of visited nodes
    """
    if term in visited_nodes:
        return (aggregator, visited_nodes)
    for subject, predicate, obj in store.triples((term, None, None)):
        # find equivalent class and recurse into the graph traversal
        if predicate == OWL.equivalentClass:
            aggregator, visited_nodes = graph_traversal(
                obj, aggregator, display_subject, visited_nodes
            )
        # find intersections of and recurse into the items of the list
        elif predicate == OWL.intersectionOf:
            for list_term in array2list(obj, []):
                aggregator, visited_nodes = graph_traversal(
                    list_term, aggregator, display_subject, visited_nodes
                )
        # check if subject is an owl restriction and hasn't been visited before
        elif (
            subject,
            RDF.type,
            OWL.Restriction,
        ) in store and subject not in visited_nodes:
            aggregator, visited_nodes = parse_owl_restrictions(
                subject, aggregator, display_subject, visited_nodes
            )
            visited_nodes.add(subject)
        visited_nodes.add(term)
    return (aggregator, visited_nodes)


def mermaid_formatter(links: List[Tuple[Node, Node, Node]]) -> str:
    """
    Takes a list of links, and formats them into a mermaid formated string
    """
    # initialize the Node structure for Mermaid
    nodes = NodeStructure()

    formatted_string = "    graph TB\n"
    for link in links:
        subject = nodes.get_node(str(link[0]))
        predicate = format_values(str(link[1]))
        obj = nodes.get_node(str(link[2]))
        formatted_string += f"      {subject} --{predicate}--> {obj}\n"

    return formatted_string


def find_instance_triples(uri: Node, instance_store: Graph):
    triples = store.triples((uri, None, None))
    for triple in triples:
        instance_store.add(triple)
        instance_store = find_instance_triples(triple[2], instance_store)
    return instance_store


def main():
    """
    The main function takes the parameters, and then calls the main functions
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-u",
        "--uri",
        type=str,
        help="the uri which should create the base for the visualization",
    )
    parser.add_argument(
        "-t", "--triples", action="store_true", help="print the triples for a given uri"
    )
    parser.add_argument(
        "rdf", nargs="+", help="the different rdf files to add to the graph"
    )
    args = parser.parse_args()

    for file in args.rdf:
        store.parse(file)

    uri = expand_prefix_uri(args.uri)
    onto_term = URIRef(uri)
    if args.triples:
        instance_store = Graph()
        instance_store = find_instance_triples(onto_term, instance_store)
        print(instance_store.serialize(format="turtle"))
        return

    agg = []
    visited_nodes = set()
    arr, _ = graph_traversal(onto_term, agg, onto_term, visited_nodes)

    mermaid = mermaid_formatter(arr)
    print(mermaid)


if __name__ == "__main__":
    import argparse

    main()
