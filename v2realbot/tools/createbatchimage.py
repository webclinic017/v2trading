import argparse
import v2realbot.reporting.metricstoolsimage as mt

##Generates BATCH REPORT again for the given batch_id
##USAGE: python createbatchimage.py <batch_id>
#Parse the command-line arguments
parser = argparse.ArgumentParser(description="Generate trading report image with batch ID")
parser.add_argument("batch_id", type=str, help="The batch ID for the report")
args = parser.parse_args()

batch_id = args.batch_id

# Generate the report image
res, val = mt.generate_trading_report_image(batch_id=batch_id)

# Print the result
if res == 0:
    print("BATCH REPORT CREATED")
else:
    print(f"BATCH REPORT ERROR - {val}")
