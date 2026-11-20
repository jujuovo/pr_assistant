"""Real-model regression; reference lab is optional and never a runtime dependency."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
from PIL import Image
BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from services.recognition.provider import PaddleProvider
from services.recognition.volunteer_material import extract, filter_platform_noise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples',type=Path,default=BACKEND/'samples/VolunteerHours')
    parser.add_argument('--reference-extractor',type=Path)
    args=parser.parse_args()
    reference=None
    if args.reference_extractor:
        spec=importlib.util.spec_from_file_location('reference_volunteer_lab',args.reference_extractor)
        reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    provider=PaddleProvider(model_root=BACKEND/'ocr-models')
    output=BACKEND/'outputs/volunteer-ocr/platform-samples';output.mkdir(parents=True,exist_ok=True)
    summary=[]
    paths=sorted(p for p in args.samples.iterdir() if p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'})
    assert paths, 'No private samples provided'
    for path in paths:
        with Image.open(path) as image:width=image.width
        page=provider.predict(path)
        report=extract(page,width)
        (output/(path.stem+'-report.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        from services.recognition.serialization import json_safe
        (output/(path.stem+'-ocr.json')).write_text(json.dumps(json_safe(page),ensure_ascii=False,indent=2),encoding='utf-8')
        expected=reference.extract(page,width) if reference else None
        fields=(report['platform_extraction'] or {}).get('fields',{})
        baseline_equal=(report['platform_baseline'] or {}).get('fields')==expected['fields'] if expected else None
        adjusted_expected=reference.extract(filter_platform_noise(page),width) if reference and report['noise_filtered'] else expected
        equal=fields==adjusted_expected['fields'] if adjusted_expected else None
        item={'file':path.name,'hours':report['fields']['hours'],'missing_fields':report['missing_fields'],'reference_fields_equal':equal,'baseline_fields_equal':baseline_equal,'noise_filtered':report['noise_filtered'],
              'check_in':report['fields'].get('check_in'),'check_out':report['fields'].get('check_out')}
        summary.append(item)
        print(json.dumps(item,ensure_ascii=True),flush=True)
        if expected:assert equal and baseline_equal,(path.name,'fields differ from lab')
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    assert all(item['hours'] is not None for item in summary),'A sample has no extracted hours'
    print('Verified samples:',len(summary))


if __name__=='__main__':main()
