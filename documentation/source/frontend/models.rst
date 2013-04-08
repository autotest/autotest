========
 Models
========

The Database Models play a major role in the RPC server. The most important
things they do:

* Define and create the database structure on the Autotest Relational Database
* Provide a object like uniform API for the Database entries

.. note:: For historical reasons, the RPC server is composed of two different
   applications, AFE and TKO. Because of that, the models are also defined in
   two different modules.

   These may soon be united into a single application, specially their model
   definition. For now, keep in mind that the model you are looking for may
   be in one of two different places.

.. toctree::
   model_logic
   afe_models
   tko_models
