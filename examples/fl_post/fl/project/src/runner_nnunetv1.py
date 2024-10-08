# Copyright (C) 2020-2021 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
Contributors: Micah Sheller, Patrick Foley, Brandon Edwards  - DELETEME?

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
                 train_cutoff=np.inf,
                 val_cutoff=np.inf,
                 nnunet_task=None,
                 config_path=None,
                 TOTAL_max_num_epochs=1000,
                 **kwargs):
        """Initialize.

        Args:
            train_cutoff (int)                  : Total time (in seconds) allowed for iterating over train batches (plus or minus one iteration since check willl be once an iteration).
            val_cutoff (int)                    : Total time (in seconds) allowed for iterating over val batches (plus or minus one iteration since check willl be once an iteration).
            nnunet_task (str)                   : Task string used to identify the data and model folders
            config_path(str)                    : Path to the configuration file used by the training and validation script.
            TOTAL_max_num_epochs (int)          : Total number of epochs for which this collaborator's model will be trained, should match the total rounds of federation in which this runner is participating
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

        self.train_cutoff = train_cutoff
        self.val_cutoff = val_cutoff
        self.config_path = config_path
        self.TOTAL_max_num_epochs=TOTAL_max_num_epochs

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

        checkpoint_dict = self.load_checkpoint(map_location=device)
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
            # see if there is state to restore first
            if tensor_dict.pop('__opt_state_needed') == 'true':
                checkpoint_dict = self._set_optimizer_state(derived_opt_state_dict=tensor_dict, 
                                                            checkpoint_dict=checkpoint_dict)
        self.save_checkpoint(checkpoint_dict)

        # FIXME: this should be unnecessary now
        # we may want to know epoch so that we can properly tell the training script to what epoch to train (NNUnet V1 only supports training with a max_num_epochs setting)
        return epoch

        
    def train(self, col_name, round_num, input_tensor_dict, epochs, **kwargs):
        # TODO: Figure out the right name to use for this method and the default assigner
        """Perform training for a specified number of epochs."""

        self.rebuild_model(input_tensor_dict=input_tensor_dict, **kwargs)
        # 1. Insert tensor_dict info into checkpoint
        current_epoch = self.set_tensor_dict(tensor_dict=input_tensor_dict, with_opt_vars=False)
        self.logger.info(f"In col train method, loaded checkpoint with current epoch: {current_epoch}")
        # 2. Train/val function existing externally
        # Some todo inside function below
        # TODO: test for off-by-one error 
        
        # FIXME: we need to understand how to use round_num instead of current_epoch
        #   this will matter in straggler handling cases
        # TODO: Should we put this in a separate process?
        # TODO: Currently allowing at most 1 second of valiation over one batch in order to avoid NNUnet code throwing exception due 
        #        to empty val results
        train_completed, \
        val_completed, \
        this_ave_train_loss, \
        this_ave_val_loss, \
        this_val_eval_metrics = train_nnunet(TOTAL_max_num_epochs=self.TOTAL_max_num_epochs, 
                                                      epochs=epochs, 
                                                      current_epoch=current_epoch, 
                                                      train_cutoff=self.train_cutoff,
                                                      val_cutoff = self.val_cutoff,
                                                      task=self.data_loader.get_task_name(),
                                                      val_epoch=True,
                                                      train_epoch=True)
        # update amount of task completed
        self.task_completed['train'] = train_completed
        self.task_completed['locally_tuned_model_validation'] = val_completed

        self.logger.info(f"Completed train/val with {int(train_completed*100)}% of the train work and {int(val_completed*100)}% of the val work. Exact rates are: {train_completed} and {val_completed}")

        # 3. Prepare metrics 
        metrics = {'train_loss': this_ave_train_loss}

        ######################################################################################################           
        # TODO:  Provide train_completed to be incorporated into the collab weight computation
        ###################################################################################################### 
        return self.convert_results_to_tensorkeys(col_name, round_num, metrics)
  

    def validate(self, col_name, round_num, input_tensor_dict, from_checkpoint=False, **kwargs):
        # TODO: Figure out the right name to use for this method and the default assigner
        """Perform validation."""

        def compare_tensor_dicts(td_1, td_2, tag="", epsilon=0.0001):
            hash_1 = np.sum([np.mean(_value) for _value in td_1.values()])
            hash_2 = np.sum([np.mean(_value) for _value in td_2.values()])
            delta = np.abs(hash_1 - hash_2)
            if delta > epsilon:
                raise VaueError(f"The tensor dict comparison {tag} failed with delta: {delta} against an accepted error of: {epsilon}.")


        if not from_checkpoint:
            self.rebuild_model(input_tensor_dict=input_tensor_dict, **kwargs)
            # 1. Insert tensor_dict info into checkpoint
            current_epoch = self.set_tensor_dict(tensor_dict=input_tensor_dict, with_opt_vars=False)
            self.logger.info(f"In col val method, loaded checkpoint with current epoch: {current_epoch}")
            # 2. Train/val function existing externally
            # Some todo inside function below
            # TODO: test for off-by-one error  
            
            # FIXME: we need to understand how to use round_num instead of current_epoch
            #   this will matter in straggler handling cases
            # TODO: Should we put this in a separate process?
            train_completed, \
            val_completed, \
            this_ave_train_loss, \
            this_ave_val_loss, \
            this_val_eval_metrics = train_nnunet(TOTAL_max_num_epochs=self.TOTAL_max_num_epochs, 
                                                epochs=1, 
                                                current_epoch=current_epoch, 
                                                train_cutoff=0,
                                                val_cutoff = self.val_cutoff,
                                                task=self.data_loader.get_task_name(), 
                                                val_epoch=True,
                                                train_epoch=False)
            # double check
            if train_completed != 0.0:
                raise ValueError(f"Tried to validate only, but got a non-zero amount ({train_completed}) of training done.")

            # update amount of task completed
            self.task_completed['aggregated_model_validation'] = val_completed

            self.logger.info(f"Completed train/val with {int(train_completed*100)}% of the train work and {int(val_completed*100)}% of the val work. Exact rates are: {train_completed} and {val_completed}")

            
            # 3. Prepare metrics 
            metrics = {'val_eval': this_val_eval_metrics}
        else:
            checkpoint_dict = self.load_checkpoint()
            # double check
            compare_tensor_dicts(td_1=input_tensor_dict,td_2=checkpoint_dict['state_dict'])

            (all_tr_losses, _, _, _) = checkpoint_dict['plot_stuff']
            # these metrics are appended to the checkpoint each call to train, so it is critical that we are grabbing this right after
            metrics = {'train_loss': all_tr_losses[-1]}

        ######################################################################################################           
        # TODO:  Provide val_completed to be incorporated into the collab weight computation
        ###################################################################################################### 
        return self.convert_results_to_tensorkeys(col_name, round_num, metrics)


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


    # TODO to support below, save train_completed and val_completed as class attributes
    # WORKING HERE, for now turned off due to task_dependent default
    
    def get_train_data_size(self, task_dependent=False, task=None):
        """Get the number of training examples.

        It will be used for weighted averaging in aggregation. 
        This overrides the parent class method,
        allowing dynamic weighting by storing recent appropriate weights in class attributes.

        Returns:
            int: The number of training examples.
        """
        if not task_dependent:
            return self.data_loader.get_train_data_size()
        elif not task:
            raise ValueError(f"If using task dependent data size, must provide task.")
        else:
            # self.task_completed is a dictionary of task to amount completed as a float in [0,1]
            return self.task_completed[task] * self.data_loader.get_train_data_size() 
