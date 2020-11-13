import subprocess
import yaml
from m2g.utils.gen_utils import run
import sys

def make_dataconfig(input_dir, sub, ses, anat, func, acquisition='alt+z', tr=2.0):
    """Generates the data_config file needed by cpac
    
    Arguments:
        input_dir {str} -- Path of directory containing input files
        sub {int} -- subject number
        ses {int} -- session number
        anat {str} -- Path of anatomical nifti file
        func {str} -- Path of functional nifti file
        acquisition {str} -- acquisition method for funcitonal scan
        tr {float} -- TR (seconds) of functional scan
    
    Returns:
        None
    """

    Data = [{
        'subject_id': sub,
        'unique_id': f'ses-{ses}',
        'anat': anat,
        'func': {
                'rest_run-1': {
			        'scan': func,
			        'scan_parameters': {
				    	'acquisition': acquisition,
				    	'tr': tr
			    }
		    }
	    }    
    }]
    
    config_file = f'{input_dir}/data_config.yaml'
    with open(config_file,'w',encoding='utf8') as outfile:
        yaml.dump(Data, outfile, default_flow_style=False)
    
    return config_file
    

def make_script(input_dir, output_dir, subject, session, data_config, pipeline_config, mem_gb, n_cpus):
    cpac_script = '/root/.m2g/cpac_script.sh'
    with open(cpac_script,'w+',encoding='utf8') as script:
        script.write(f'''#! /bin/bash
        python3.6 /code/run.py --data_config_file {data_config} --pipeline_file {pipeline_config} --n_cpus {n_cpus} --mem_gb {mem_gb} {input_dir} {output_dir} participant
        ''')
    
    run(f'chmod +x {cpac_script}')

    return cpac_script



def m2g_func_worker(input_dir, output_dir, sub, ses, anat, bold, acquisition, tr, mem_gb, n_cpus):
    """Creates the requisite files to run CPAC, then calls CPAC and runs it in a terminal
    
    Arguments:
        input_dir {str} -- Path to input directory
        output_dir {str} -- Path to output directory
        sub {int} -- subject number
        ses {int} -- session number
        anat {str} -- Path of anatomical nifti file
        bold {str} -- Path of functional nifti file
        acquisition {str} -- Acquisition method for funcitional scans
        tr {str} -- TR time, in seconds
    """
    
    pipeline_config='/m2g/m2g/functional/m2g_pipeline.yaml'
    
    data_config = make_dataconfig(input_dir, sub, ses, anat, bold, acquisition, tr)
    cpac_script = make_script(input_dir, output_dir, sub, ses, data_config, pipeline_config,mem_gb, n_cpus)
    
    # Run pipeline
    subprocess.call([cpac_script], shell=True)
