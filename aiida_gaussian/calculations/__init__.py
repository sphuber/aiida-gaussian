# -*- coding: utf-8 -*-
"""Gaussian input plugin."""
from __future__ import absolute_import
import os
from shutil import copyfile, copytree
import six
from six.moves import map, range

from aiida.orm import Dict, FolderData, List, RemoteData, SinglefileData
from aiida.common import CalcInfo, CodeInfo, InputValidationError
#from aiida.cmdline.utils import echo
from aiida.engine import CalcJob
from aiida.plugins import DataFactory

import pymatgen as mg
import pymatgen.io.gaussian as mgaus

StructureData = DataFactory('structure')

class GaussianCalculation(CalcJob):
    """AiiDA calculation plugin wrapping Gaussian"""
    # Defaults
    INPUT_FILE = 'aiida.gjf'
    OUTPUT_FILE = 'aiida.log'
    CHK_FILE = 'aiida.chk'
    PROJECT_NAME = 'aiida'
    DEFAULT_PARSER = 'gaussian_base_parser'

    @classmethod
    def define(cls, spec):
        super(GaussianCalculation, cls).define(spec)

        #Input parameters
        spec.input('structure',
            valid_type=StructureData,
            required=True,
            help='Input passed as pymatgen_molecule object')

        # spec.input('charge', valid_type=Int, required=True, help='charge of the system')
        # spec.input('multiplicity', valid_type=Int, required=True, help='spin multiplicity of the system')

        spec.input('parameters', valid_type=Dict, required=True, help='Input parameters')
        spec.input('settings', valid_type=Dict, required=False, help='additional input parameters')

        # spec.input_namespace(
        #         'parameters',
        #         valid_type=Dict,
        #         required=False,
        #         dynamic=True,
        #         help='Parameters such as functional and basis-set!')
        # spec.input_namespace(
        #         'general_params',
        #         valid_type=Dict,
        #         required=False,
        #         dynamic=True,
        #         help='Parameters such as functional and basis-set!')
        # spec.input_namespace(
        #         'route_params',
        #         valid_type=Dict,
        #         required=False,
        #         dynamic=True,
        #         help='Parameters for the route section')
        # spec.input_namespace(
        #         'input_params',
        #         valid_type=Dict,
        #         required=False,
        #         dynamic=True,
        #         help='Parameters for defining input parameters which come after coordinates.')
        # spec.input_namespace(
        #         'link0_params',
        #         valid_type=Dict,
        #         required=False,
        #         dynamic=True,
        #         help='Parameters for the Link0(%) section')

        # Turn mpi off by default
        spec.input('metadata.options.withmpi', valid_type=bool, default=False)

        spec.input('metadata.options.parser_name', valid_type=six.string_types, default=cls.DEFAULT_PARSER, non_db=True)

        # Outputs
        spec.output('output_parameters', valid_type=Dict, required=True, help="The result parameters of the calculation")
        spec.output('output_structure', valid_type=StructureData, required=False, help="Final optimized structure, if available")

        spec.default_output_node = 'output_parameters'

        # Exit codes
        spec.exit_code(100, 'ERROR_MISSING_OUTPUT_FILES', message='Calculation did not produce all expected output files.')


    # --------------------------------------------------------------------------
    # pylint: disable = too-many-locals
    def prepare_for_submission(self, folder):
        """
        This is the routine to be called when you want to create
        the input files and related stuff with a plugin.

        :param folder: a aiida.common.folders.Folder subclass where
                           the plugin should put all its files.
        """
        # create calc info
        calcinfo = CalcInfo()
        calcinfo.remote_copy_list = []
        calcinfo.local_copy_list = []

        # initialize input parameters
        # inp = GaussianInput(self.inputs.parameters.get_dict())

        # Getting the structure, charge and spin multiplicity
        strc = self.inputs.structure.get_pymatgen_molecule()
        charge = strc.charge
        multiplicity = strc.spin_multiplicity

        # construct the input file.
        provided_params = self.inputs.parameters.get_dict()

        if 'route_parameters' in provided_params:
            route_params = provided_params['route_parameters']
        else:
            route_params = None

        if 'input_parameters' in provided_params:
            input_params = provided_params['input_parameters']
        else:
            input_params = None

        if 'link0_parameters' in provided_params:
            link0_params = provided_params['link0_parameters']
        else:
            link0_params = None


        inp = mgaus.GaussianInput(
                strc,
                charge=charge,
                spin_multiplicity=multiplicity,
                title='Gaussian Input File Generated by AiiDA via AiiDA-Gaussian Plugin',
                functional=provided_params['functional'],
                basis_set=provided_params['basis_set'],
                route_parameters= route_params,
                input_parameters=input_params,
                link0_parameters=link0_params,
                dieze_tag='#P'
                )

        inp.write_file(folder.get_abs_path(self.INPUT_FILE), cart_coords=True)

        settings = self.inputs.settings.get_dict() if 'settings' in self.inputs else {}

        # create code info
        codeinfo = CodeInfo()
        codeinfo.cmdline_params = settings.pop('cmdline', [])
        codeinfo.code_uuid = self.inputs.code.uuid
        codeinfo.stdin_name = self.INPUT_FILE
        codeinfo.stdout_name = self.OUTPUT_FILE
        codeinfo.withmpi = self.inputs.metadata.options.withmpi

        # create calculation info
        calcinfo.uuid = self.uuid
        calcinfo.cmdline_params = codeinfo.cmdline_params
        calcinfo.stdin_name = self.INPUT_FILE
        calcinfo.stdout_name = self.OUTPUT_FILE
        calcinfo.codes_info = [codeinfo]
        calcinfo.retrieve_list = [self.OUTPUT_FILE]


        return calcinfo
