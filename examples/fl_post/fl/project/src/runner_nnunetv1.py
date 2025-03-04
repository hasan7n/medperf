# Copyright (C) 2020-2021 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
Contributors: Micah Sheller, Patrick Foley, Brandon Edwards

"""
# TODO: Clean up imports

import os
import subprocess
import shutil
import time
import pickle as pkl
from copy import deepcopy
import hashlib
import yaml

import numpy as np
import torch

from openfl.utilities import TensorKey
from openfl.utilities.split import split_tensor_dict_for_holdouts


from .runner_pt_chkpt import PyTorchCheckpointTaskRunner
from .nnunet_v1 import train_nnunet

shared_plans_identifier = 'nnUNetPlans_pretrained_POSTOPP'

class PyTorchNNUNetCheckpointTaskRunner(PyTorchCheckpointTaskRunner):
    """An abstract class for PyTorch model based Tasks, where training, validation etc. are processes that
       pull model state from a PyTorch checkpoint."""

    def __init__(self,
                 nnunet_task=None,
                 config_path=None,
                 actual_max_num_epochs=1000,
                 **kwargs):
        """Initialize.

        Args:
            nnunet_task (str)                   : Task string used to identify the data and model folders
            config_path(str)                    : Path to the configuration file used by the training and validation script.
            actual_max_num_epochs (int)         : Number of epochs for which this collaborator's model will be trained, should match the total rounds of federation in which this runner is participating
            kwargs                              : Additional key work arguments (will be passed to rebuild_model, initialize_tensor_key_functions, TODO: <Fill this in>).
            TODO: 
        """ 
        
        if 'nnUNet_raw_data_base' not in os.environ:
            raise ValueError("NNUNet V1 requires that 'nnUNet_raw_data_base' be set either in the flplan or in the environment variables")
        if 'nnUNet_preprocessed' not in os.environ:
            raise ValueError("NNUNet V1 requires that 'nnUNet_preprocessed' be set either in the flplan or in the environment variables")
        if 'RESULTS_FOLDER' not in os.environ:
            raise ValueError("NNUNet V1 requires that 'RESULTS_FOLDER' be set either in the flplan or in the environment variables")

        super().__init__(
            checkpoint_path_initial=os.path.join(
                os.environ['RESULTS_FOLDER'], 
                f'nnUNet/3d_fullres/{nnunet_task}/nnUNetTrainerV2__{shared_plans_identifier}/fold_0/',
                'model_initial_checkpoint.model'
                ),
            checkpoint_path_save=os.path.join(
                os.environ['RESULTS_FOLDER'], 
                f'nnUNet/3d_fullres/{nnunet_task}/nnUNetTrainerV2__{shared_plans_identifier}/fold_0/',
                'model_final_checkpoint.model'
                ),
            checkpoint_path_load=os.path.join(
                os.environ['RESULTS_FOLDER'], 
                f'nnUNet/3d_fullres/{nnunet_task}/nnUNetTrainerV2__{shared_plans_identifier}/fold_0/',
                'model_final_checkpoint.model'
                ),
            **kwargs,
            )

        self.config_path = config_path
        self.actual_max_num_epochs=actual_max_num_epochs

        # self.task_completed is a dictionary of task to amount completed as a float in [0,1]
        # Values will be dynamically updated
        # TODO: Tasks are hard coded for now
        self.task_completed = {'aggregated_model_validation': 1.0, 
                               'train': 1.0, 
                               'locally_tuned_model_validation': 1.0}
        
    
    def write_tensors_into_checkpoint(self, tensor_dict, with_opt_vars):
        """
        Save model state in tensor_dict to in a pickle file at self.checkpoint_out_path. Uses pt.save(). 
        All state in the checkpoint other than the model state will be kept as is in the file.
        Note: Utilization of a with_opt_vars input will be needed (along with saving an initial state optimizer state on disk),
              will be needed if a self.opt_treatement of 'RESET' or 'AGG' are to be used 
        
            Here is an example of a dictionary NNUnet uses for its state:
            save_this = 
                {
                'epoch': self.epoch + 1,
                'state_dict': state_dict,
                'optimizer_state_dict': optimizer_state_dict,
                'lr_scheduler_state_dict': lr_sched_state_dct,
                'plot_stuff': (self.all_tr_losses, self.all_val_losses, self.all_val_losses_tr_mode,
                           self.all_val_eval_metrics),
                'best_stuff' : (self.best_epoch_based_on_MA_tr_loss, self.best_MA_tr_loss_for_patience, self.best_val_eval_criterion_MA)
                }


        Args:
            tensor_dict (dictionary)                 : Dictionary with keys 
            with_opt_vars (bool)                : Whether or not to save the optimizer state as well (this info will be part of the tensor dict in this case - i.e. tensor_dict = {**model_state, **opt_state})
            kwargs                            : unused

        Returns:
            epoch
        """
        # TODO: For now leaving the lr_scheduler_state_dict unchanged (this may be best though)
        # TODO: Do we want to test this for 'RESET', 'CONTINUE_GLOBAL'?

        # get device for correct placement of tensors
        device = self.device
        self.logger.info('loading checkpoint, due to set tensor call.')
        checkpoint_dict = self.load_checkpoint(checkpoint_path=self.checkpoint_path_load, map_location=device)
        epoch = checkpoint_dict['epoch']
        new_state = {}
        # grabbing keys from the checkpoint state dict, poping from the tensor_dict
        seen_keys = []
        for k in checkpoint_dict['state_dict']:
            if k not in seen_keys:
                seen_keys.append(k)
            else:
                raise ValueError(f"\nKey {k} apears at least twice!!!!/n")
            new_state[k] = torch.from_numpy(tensor_dict[k].copy()).to(device)
        checkpoint_dict['state_dict'] = new_state
        
        if with_opt_vars:
            self.logger.info('maybe set optimizer state')
            # see if there is state to restore first
            if tensor_dict.pop('__opt_state_needed') == 'true':
                checkpoint_dict = self._set_optimizer_state(derived_opt_state_dict=tensor_dict, 
                                                            checkpoint_dict=checkpoint_dict)
        self.logger.info('save checkpoint')
        self.save_checkpoint(checkpoint_dict)
        self.logger.info('done save checkpoint')

        # FIXME: this should be unnecessary now
        # we may want to know epoch so that we can properly tell the training script to what epoch to train (NNUnet V1 only supports training with a max_num_epochs setting)
        return epoch

        
    def train(self, col_name, round_num, input_tensor_dict, epochs, val_cutoff_time=np.inf, train_cutoff_time=np.inf, train_completion_dampener=0.0, **kwargs):
        # TODO: Figure out the right name to use for this method and the default assigner
        """Perform training for a specified number of epochs."""

        global_tensor_dict = {}
        local_tensor_dict = {}
        the_file = os.path.join(os.path.dirname(__file__), "to_send.yaml")
        with open(the_file) as f:
            req = yaml.safe_load(f)
        for k in req:
            tk = TensorKey(k["tensor_name"], k["origin"], round_num, k["report"], tuple(k["tags"]))
            global_tensor_dict[tk] = np.random.random(size=k["val_shape"]).astype(k["val_type"])

        local_tensor_dict[TensorKey("__opt_state_needed", col_name, round_num, False, ("trained",))] = "true"
        local_tensor_dict[TensorKey("__opt_state_needed", col_name, round_num+1, False, ("model",))] = "true"

        return global_tensor_dict, local_tensor_dict
  

    def validate(self, col_name, round_num, input_tensor_dict, val_cutoff_time=np.inf, from_checkpoint=False, **kwargs):
        # TODO: Figure out the right name to use for this method and the default assigner
        """Perform validation."""
        local_output_tensor_dict = {}
        global_output_tensor_dict = {}

        metrics = {'val_eval': np.random.random(size=[]).astype(np.float64), 
                       'val_eval_C1': np.random.random(size=[]).astype(np.float64), 
                       'val_eval_C2': np.random.random(size=[]).astype(np.float64), 
                       'val_eval_C3': np.random.random(size=[]).astype(np.float64), 
                       'val_eval_C4': np.random.random(size=[]).astype(np.float64)}
        tags = ("metric", f"nnunet_{kwargs['apply']}_val")
        
        for m in metrics:
            tk = TensorKey(m, col_name, round_num, True, tags)
            global_output_tensor_dict[tk] = metrics[m]

        return global_output_tensor_dict, local_output_tensor_dict


    def load_metrics(self, filepath):
        """
        Load metrics from file on disk
        """
        raise NotImplementedError()
        """
        with open(filepath) as json_file:
            metrics = json.load(json_file)
        return metrics
        """


    def get_train_data_size(self, task_name=None):
        """Get the number of training examples.

        It will be used for weighted averaging in aggregation. 
        This overrides the parent class method,
        allowing dynamic weighting by storing recent appropriate weights in class attributes.

        Returns:
            int: The number of training examples, weighted by how much of the task got completed, then cast to int to satisy proto schema
        """
        if not task_name:
            return self.data_loader.get_train_data_size()
        else:
            # self.task_completed is a dictionary of task_name to amount completed as a float in [0,1]
            return int(np.ceil(self.task_completed[task_name]**(-1) * self.data_loader.get_train_data_size()))


    def get_valid_data_size(self, task_name=None):
        """Get the number of training examples.

        It will be used for weighted averaging in aggregation. 
        This overrides the parent class method,
        allowing dynamic weighting by storing recent appropriate weights in class attributes.

        Returns:
            int: The number of training examples, weighted by how much of the task got completed, then cast to int to satisy proto schema
        """
        if not task_name:
            return self.data_loader.get_valid_data_size()
        else:
            # self.task_completed is a dictionary of task_name to amount completed as a float in [0,1]
            return int(np.ceil(self.task_completed[task_name]**(-1) * self.data_loader.get_valid_data_size()))  
