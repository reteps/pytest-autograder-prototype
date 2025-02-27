# Run student code

# Run pytest
# Collect and parse results

import subprocess
from xml.etree import ElementTree
from dataclasses import dataclass
from typing import TypedDict
from datetime import datetime
import json

@dataclass
class Property:
    name: str
    value: str

@dataclass
class TestCaseFailure:
    message: str
    trace: str
@dataclass
class TestCase:
    classname: str
    name: str
    time: float
    points: int
    failure: TestCaseFailure

@dataclass
class TestSuite:
    name: str
    errors: int
    failures: int
    skipped: int
    tests: int
    time: float
    timestamp: datetime
    hostname: str
    testcases: list[TestCase]

@dataclass
class TestSuites:
    testsuites: list[TestSuite]

def parse_xml(root) -> TestSuites:
    testsuites_list = []
    for testsuite_elem in root.findall('./testsuite'):
        testcases = []
        for testcase_elem in testsuite_elem.findall('./testcase'):
            properties_elem = testcase_elem.find('./properties')
            properties = None
            if properties_elem is not None:
                properties = {}
                for prop_elem in properties_elem.findall('./property'):
                    properties[prop_elem.get('name')] = prop_elem.get('value')
            failure_elem = testcase_elem.find('./failure')
            failure = None
            if failure_elem is not None:
                failure = TestCaseFailure(
                    message=failure_elem.get('message'),
                    trace=failure_elem.text
                )
            testcases.append(TestCase(
                classname=testcase_elem.get('classname'),
                name=properties.get('name') or testcase_elem.get('name'),
                time=float(testcase_elem.get('time')),
                points=float(properties.get('points', 1)),
                failure=failure
            ))
        
        testsuites_list.append(TestSuite(
            name=testsuite_elem.get('name'),
            errors=int(testsuite_elem.get('errors')),
            failures=int(testsuite_elem.get('failures')),
            skipped=int(testsuite_elem.get('skipped')),
            tests=int(testsuite_elem.get('tests')),
            time=float(testsuite_elem.get('time')),
            timestamp=datetime.fromisoformat(testsuite_elem.get('timestamp')),
            hostname=testsuite_elem.get('hostname'),
            testcases=testcases
        ))
    
    return TestSuites(testsuites_list)

subprocess.Popen([
    "python3",
    "student_code.py"
], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

process = subprocess.Popen([
    "pytest",
    "--junit-xml=out.xml"
], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout, stderr = process.communicate()
print(stdout.decode())
print(stderr.decode())

tree = ElementTree.parse("out.xml")
doc = tree.getroot()
parsed = parse_xml(doc)
print(parsed)

class TestResult(TypedDict, total=False):
    name: str
    description: str
    points: float
    max_points: float
    output: str
    message: str

class PartialResult(TypedDict):
    points: float
    max_points: float

class OverallResult(TypedDict):
    points: float
    max_points: float
    tests: list[TestResult]
    partial_scores: dict[str, PartialResult]

def create_overall_result(parsed: TestSuites) -> OverallResult:
    tests: list[TestResult] = []
    partial_scores: dict[str, PartialResult] = {}
    total_points = 0
    total_max_points = 0
    
    for testsuite in parsed.testsuites:
        for testcase in testsuite.testcases:
            # Create TestResult for each test case
            test_result: TestResult = {
                "name": testcase.name,
                "points": testcase.points if testcase.failure is None else 0,
                "max_points": testcase.points,
            }
            if testcase.failure is not None:
                test_result["output"] = testcase.failure.message
            
            # Add to tests list
            tests.append(test_result)
            
            # Update total points
            total_points += test_result["points"]
            total_max_points += test_result["max_points"]

    # Create the final OverallResult
    overall_result: OverallResult = {
        "points": total_points,
        "max_points": total_max_points,
        "tests": tests,
        "partial_scores": partial_scores
    }
    
    return overall_result
# Construct the overallresult object

with open("results.json", "w") as f:
    f.write(json.dumps(create_overall_result(parsed), indent=2))