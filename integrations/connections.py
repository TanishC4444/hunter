import argparse
import json
from urllib.parse import urlencode


def searches(company, school="University of Texas at Austin"):
    company = company.replace('"', '')
    school = school.replace('"', '')
    terms = {"alumni": f'"{school}"', "former_interns": '"intern"',
             "engineers": '("software engineer" OR "machine learning engineer")',
             "recruiters": '("recruiter" OR "university recruiting")'}
    return {kind: "https://www.google.com/search?" + urlencode({"q": f'site:linkedin.com/in "{company}" {term}'})
            for kind, term in terms.items()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate people-search links; no scraping or messaging")
    parser.add_argument("company")
    parser.add_argument("--school", default="University of Texas at Austin")
    args = parser.parse_args()
    print(json.dumps(searches(args.company, args.school), indent=2))
