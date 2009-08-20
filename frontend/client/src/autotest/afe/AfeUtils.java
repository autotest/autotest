package autotest.afe;

import autotest.afe.CreateJobView.JobCreateListener;
import autotest.common.JSONArrayList;
import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.SimpleCallback;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.table.JSONObjectSet;
import autotest.common.table.ListFilter;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.RadioChooser;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONBoolean;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Iterator;
import java.util.List;
import java.util.Set;

/**
 * Utility methods.
 */
public class AfeUtils {
    public static final String PLATFORM_SUFFIX = " (platform)";
    private static final String ALL_USERS = "All Users";
    public static final String ATOMIC_GROUP_SUFFIX = " (atomic group)";
    public static final String REINSTALL_TEST_NAME = "Re-install Machine";
    
    public static final ClassFactory factory = new SiteClassFactory();

    private static StaticDataRepository staticData = StaticDataRepository.getRepository();
    
    public static String formatStatusCounts(JSONObject counts, String joinWith) {
        String result = "";
        Set<String> statusSet = counts.keySet();
        for (Iterator<String> i = statusSet.iterator(); i.hasNext();) {
            String status = i.next();
            int count = (int) counts.get(status).isNumber().doubleValue();
            result += Integer.toString(count) + " " + status;
            if (i.hasNext())
                result += joinWith;
        }
        return result;
    }
    
    public static String[] getLabelStrings() {
        return getFilteredLabelStrings(false, false);
    }
    
    protected static String[] getFilteredLabelStrings(boolean onlyPlatforms,
                                                      boolean onlyNonPlatforms) {
        assert( !(onlyPlatforms && onlyNonPlatforms));
        JSONArray labels = staticData.getData("labels").isArray();
        List<String> result = new ArrayList<String>();
        for (int i = 0; i < labels.size(); i++) {
            JSONObject label = labels.get(i).isObject();
            String name = label.get("name").isString().stringValue();
            boolean labelIsPlatform = label.get("platform").isBoolean().booleanValue();
            JSONObject atomicGroup = label.get("atomic_group").isObject();
            if (atomicGroup != null) {
                name += ATOMIC_GROUP_SUFFIX;
            }
            if ((onlyPlatforms && labelIsPlatform) ||
                (onlyNonPlatforms && !labelIsPlatform)) {
                    result.add(name);
            } else if (!onlyPlatforms && !onlyNonPlatforms) {
                if (labelIsPlatform) {
                    name += PLATFORM_SUFFIX;
                }
                result.add(name);
            }
        }
        return result.toArray(new String[result.size()]);
    }

    public static String[] getPlatformStrings() {
        return getFilteredLabelStrings(true, false);
    }
    
    public static String[] getNonPlatformLabelStrings() {
        return getFilteredLabelStrings(false, true);
    }

    public static String decodeLabelName(String labelName) {
        String name = labelName;
        if (name.endsWith(PLATFORM_SUFFIX)) {
            int nameLength = name.length() - PLATFORM_SUFFIX.length();
            name = name.substring(0, nameLength);
        }
        if (name.endsWith(ATOMIC_GROUP_SUFFIX)) {
            int nameLength = name.length() - ATOMIC_GROUP_SUFFIX.length();
            name = name.substring(0, nameLength);
        }
        return name;
    }

    public static JSONString getLockedText(JSONObject host) {
        boolean locked = host.get("locked").isBoolean().booleanValue();
        return new JSONString(locked ? "Yes" : "No");
    }
    
    public static void abortHostQueueEntries(Collection<JSONObject> entries, 
                                             final SimpleCallback onSuccess) {
        if (entries.isEmpty()) {
            NotifyManager.getInstance().showError("No entries selected to abort");
            return;
        }
        
        final JSONArray asynchronousEntryIds = new JSONArray();
        Set<JSONObject> synchronousEntries = new JSONObjectSet<JSONObject>();
        for (JSONObject entry : entries) {
            JSONObject job = entry.get("job").isObject();
            int synchCount = (int) job.get("synch_count").isNumber().doubleValue();
            boolean hasExecutionSubdir = 
                !Utils.jsonToString(entry.get("execution_subdir")).equals("");
            if (synchCount > 1 && hasExecutionSubdir) {
                synchronousEntries.add(entry);
                continue;
            }

            JSONValue idListValue = entry.get("id_list");
            if (idListValue != null) {
                // metahost row
                extendJsonArray(asynchronousEntryIds, idListValue.isArray());
            } else {
                asynchronousEntryIds.set(asynchronousEntryIds.size(), entry.get("id"));
            }
        }
        
        SimpleCallback abortAsynchronousEntries = new SimpleCallback() {
            public void doCallback(Object source) {
                JSONObject params = new JSONObject();
                params.put("id__in", asynchronousEntryIds);
                AfeUtils.callAbort(params, onSuccess);
            }
        };
        
        if (synchronousEntries.size() == 0) {
            abortAsynchronousEntries.doCallback(null);
        } else {
            AbortSynchronousDialog dialog = new AbortSynchronousDialog(
                abortAsynchronousEntries, synchronousEntries, asynchronousEntryIds.size() != 0);
            dialog.center();
        }
    }

    private static void extendJsonArray(JSONArray array, JSONArray newValues) {
        for (JSONValue value : new JSONArrayList<JSONValue>(newValues)) {
            array.set(array.size(), value);
        }
    }
    
    public static void callAbort(JSONObject params, final SimpleCallback onSuccess,
                                 final boolean showMessage) {
        JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
        rpcProxy.rpcCall("abort_host_queue_entries", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                if (showMessage) {
                    NotifyManager.getInstance().showMessage("Jobs aborted");
                }
                if (onSuccess != null) {
                    onSuccess.doCallback(null);
                }
            }
        });
    }
    
    public static void callAbort(JSONObject params, final SimpleCallback onSuccess) {
        callAbort(params, onSuccess, true);
    }
    
    public static void callReverify(JSONObject params, final SimpleCallback onSuccess,
                                    final String messagePrefix) {
        JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
        rpcProxy.rpcCall("reverify_hosts", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                
                NotifyManager.getInstance().showMessage(
                        messagePrefix + " scheduled for reverification");
                    
                if (onSuccess != null) {
                    onSuccess.doCallback(null);
                }
            }
        });
    }
    
    private static void scheduleReinstallHelper(JSONArray hosts, JSONObject controlInfo,
                                                final String messagePrefix,
                                                final JobCreateListener listener) {
        String name = "reinstall_" + hosts.get(0).isString().stringValue();
        if (hosts.size() > 1) {
            name += "_etc";
        }
        
        // Get the option for "Never"
        JSONValue rebootBefore = staticData.getData("reboot_before_options").isArray().get(0);
        JSONValue rebootAfter = staticData.getData("reboot_after_options").isArray().get(0);
        
        JSONObject args = new JSONObject();
        args.put("name", new JSONString(name));
        args.put("priority", staticData.getData("default_priority"));
        args.put("control_file", controlInfo.get("control_file"));
        args.put("control_type", new JSONString(TestSelector.SERVER_TYPE));
        args.put("synch_count", controlInfo.get("synch_count"));
        args.put("timeout", staticData.getData("job_timeout_default"));
        args.put("max_runtime_hrs", staticData.getData("job_max_runtime_hrs_default"));
        args.put("run_verify", JSONBoolean.getInstance(false));
        args.put("parse_failed_repair", JSONBoolean.getInstance(true));
        args.put("reboot_before", rebootBefore);
        args.put("reboot_after", rebootAfter);
        args.put("hosts", hosts);
        
        JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
        rpcProxy.rpcCall("create_job", args, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                NotifyManager.getInstance().showMessage(messagePrefix + " scheduled for reinstall");
                if (listener != null) {
                    listener.onJobCreated((int) result.isNumber().doubleValue());
                }
            }
        });
    }
    
    public static void scheduleReinstall(final JSONArray hosts, final String messagePrefix,
                                         final JobCreateListener listener) {
        // Find the test
        JSONArray tests = staticData.getData("tests").isArray();
        JSONObject reinstallTest = null;
        for (int i = 0; i < tests.size(); i++) {
            JSONObject test = tests.get(i).isObject();
            if (test.get("name").isString().stringValue().equals(REINSTALL_TEST_NAME)) {
                reinstallTest = test;
                break;
            }
        }
        
        if (reinstallTest == null) {
            NotifyManager.getInstance().showError("No test found: " + REINSTALL_TEST_NAME);
            return;
        }
        
        JSONObject params = new JSONObject();
        JSONArray array = new JSONArray();
        JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
        
        array.set(0, reinstallTest.get("id"));
        params.put("tests", array);
        rpcProxy.rpcCall("generate_control_file", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue controlInfo) {
                scheduleReinstallHelper(hosts, controlInfo.isObject(),
                                        messagePrefix, listener);
            }
        });
    }
    
    public static void callModifyHosts(JSONObject params, final SimpleCallback onSuccess) {
        JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
        rpcProxy.rpcCall("modify_hosts", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                if (onSuccess != null) {
                    onSuccess.doCallback(null);
                }
            }
        });
    }
    
    public static void changeHostLocks(JSONArray hostIds, final boolean lock,
                                       final String messagePrefix, final SimpleCallback callback) {
        JSONObject hostFilterData = new JSONObject();
        JSONObject updateData = new JSONObject();
        JSONObject params = new JSONObject();
        
        hostFilterData.put("id__in", hostIds);
        updateData.put("locked", JSONBoolean.getInstance(lock));
        
        params.put("host_filter_data", hostFilterData);
        params.put("update_data", updateData);
        
        callModifyHosts(params, new SimpleCallback() {
            public void doCallback(Object source) {
                String message = messagePrefix + " ";
                if (!lock) {
                    message += "un";
                }
                message += "locked";
                
                NotifyManager.getInstance().showMessage(message);
                
                callback.doCallback(source);
            }
        });
    }

    public static String getJobTag(JSONObject job) {
        return Utils.jsonToString(job.get("id")) + "-" + Utils.jsonToString(job.get("owner"));
    }

    public static void populateRadioChooser(RadioChooser chooser, String name) {
        JSONArray options = staticData.getData(name + "_options").isArray();
        for (JSONString jsonOption : new JSONArrayList<JSONString>(options)) {
            chooser.addChoice(Utils.jsonToString(jsonOption));
        }
    }

    public static int parsePositiveIntegerInput(String input, String fieldName) {
        final int parsedInt;
        try {
            if (input.equals("") ||
                (parsedInt = Integer.parseInt(input)) <= 0) {
                    String error = "Please enter a positive " + fieldName;
                    NotifyManager.getInstance().showError(error);
                    throw new IllegalArgumentException();
            }
        } catch (NumberFormatException e) {
            String error = "Invalid " + fieldName + ": \"" + input + "\"";
            NotifyManager.getInstance().showError(error);
            throw new IllegalArgumentException();
        }
        return parsedInt;
    }

    public static void removeSecondsFromDateField(JSONObject row,
                                                  String sourceFieldName,
                                                  String targetFieldName) {
        JSONValue dateValue = row.get(sourceFieldName);
        String date = "";
        if (dateValue.isNull() == null) {
            date = dateValue.isString().stringValue();
            date = date.substring(0, date.length() - 3);
        }
        row.put(targetFieldName, new JSONString(date));
    }

    public static ListFilter getUserFilter(String field) {
        ListFilter userFilter = new ListFilter(field);
        userFilter.setMatchAllText(ALL_USERS);

        JSONArray userArray = staticData.getData("users").isArray();
        String[] userStrings = Utils.JSONObjectsToStrings(userArray, "login");
        userFilter.setChoices(userStrings);
        String currentUser = staticData.getCurrentUserLogin();
        userFilter.setSelectedChoice(currentUser);

        return userFilter;
    }
}
