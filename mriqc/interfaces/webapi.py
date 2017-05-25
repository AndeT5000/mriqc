#!/usr/bin/env python
# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
from __future__ import print_function, division, absolute_import, unicode_literals

from nipype import logging
from nipype.interfaces.base import (Bunch, traits, isdefined, TraitedSpec,
                                    BaseInterfaceInputSpec, File, Str)
from niworkflows.interfaces.base import SimpleInterface


IFLOGGER = logging.getLogger('interface')

SECRET_KEY = """\
ZUsBaabr6PEbav5DKAHIODEnwpwC58oQTJF7KWvDBPUmBIVFFtw\
Od7lQBdz9r9ulJTR1BtxBDqDuY0owxK6LbLB1u1b64ZkIMd46\
"""

# metadata whitelist
META_WHITELIST = [
    "ContrastBolusIngredient", "RepetitionTime", "TaskName", "Manufacturer",
    "ManufacturersModelName", "MagneticFieldStrength", "DeviceSerialNumber",
    "SoftwareVersions", "HardcopyDeviceSoftwareVersion", "ReceiveCoilName",
    "GradientSetType", "MRTransmitCoilSequence", "MatrixCoilMode",
    "CoilCombinationMethod", "PulseSequenceType", "PulseSequenceDetails",
    "NumberShots", "ParallelReductionFactorInPlane", "ParallelAcquisitionTechnique",
    "PartialFourier", "PartialFourierDirection", "PhaseEncodingDirection",
    "EffectiveEchoSpacing", "TotalReadoutTime",
    "EchoTime", "InversionTime", "SliceTiming", "SliceEncodingDirection",
    "NumberOfVolumesDiscardedByScanner", "NumberOfVolumesDiscardedByUser",
    "DelayTime", "FlipAngle", "MultibandAccelerationFactor", "Instructions",
    "TaskDescription", "CogAtlasID", "CogPOID", "InstitutionName",
    "InstitutionAddress", "ConversionSoftware", "ConversionSoftwareVersion",
    "md5sum", "modality", "mriqc_pred", "software", "subject_id", "version",
]

class UploadIQMsInputSpec(BaseInterfaceInputSpec):
    in_iqms = File(exists=True, mandatory=True, desc='the input IQMs-JSON file')
    address = Str(mandatory=True, desc='ip address listening')
    port = traits.Int(mandatory=True, desc='MRIQCWebAPI service port')
    email = Str(desc='set sender email')
    strict = traits.Bool(False, usedefault=True,
                         desc='crash if upload was not succesfull')


class UploadIQMs(SimpleInterface):
    """
    Upload features to MRIQCWebAPI
    """

    input_spec = UploadIQMsInputSpec
    output_spec = TraitedSpec

    def _run_interface(self, runtime):
        email = None
        if isdefined(self.inputs.email):
            email = self.inputs.email

        response = upload_qc_metrics(
            self.inputs.in_iqms,
            self.inputs.address,
            self.inputs.port,
            email
        )

        if response.status_code == 201:
            IFLOGGER.info('QC metrics successfully uploaded.')
            return runtime

        errmsg = 'QC metrics failed to upload. Status %d: %s' % (
            response.status_code, response.text)
        IFLOGGER.warn(errmsg)
        if self.inputs.strict:
            raise RuntimeError(response.text)

        return runtime


def upload_qc_metrics(in_iqms, addr, port, email=None):
    """
    Upload qc metrics to remote repository.

    :param str in_iqms: Path to the qc metric json file as a string
    :param str email: email address to be included with the metric submission
    :param bool no_sub: Flag from settings indicating whether or not metrics should be submitted.
        If False, metrics will be submitted. If True, metrics will not be submitted.
    :param str mriqc_webapi: the default mriqcWebAPI url
    :param bool upload_strict: the client should fail if it's strict mode

    :return: either the response object if a response was successfully sent
             or it returns the string "No Response"
    :rtype: object


    """
    from json import load, dumps
    import requests
    from io import open

    with open(in_iqms, 'r') as input_json:
        in_data = load(input_json)

    # flatten data
    data = {k: v for k, v in list(in_data.items()) if k != 'metadata'}


    modality = in_data['metadata'].get('modality', 'None')
    if modality not in ('T1w', 'bold'):
        errmsg = ('Submitting to MRIQCWebAPI: image modality should be "bold" or "T1w", '
                  '(found "%s")' % modality)
        return Bunch(status_code=1, text=errmsg)

    # Filter Metadata values that aren't in whitelist
    try:
        data.update({k: v for k, v in list(
            in_data['metadata'].items()) if k in META_WHITELIST})
    except KeyError:
        pass

    # Preemptively adding code to handle settings
    try:
        data.update({k: v for k, v in list(
            in_data['settings'].items()) if k in META_WHITELIST})
    except KeyError:
        pass

    if email:
        data['email'] = email

    headers = {'token': SECRET_KEY, "Content-Type": "application/json"}
    try:
        # if the modality is bold, call "bold" endpointt
        response = requests.post(
            'http://{}:{}/{}'.format(addr, port, modality),
            headers=headers, data=dumps(data))
    except requests.ConnectionError as err:
        errmsg = 'QC metrics failed to upload due to connection error shown below:\n%s' % err
        return Bunch(status_code=1, text=errmsg)

    return response
