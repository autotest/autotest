package autotest.afe;

import autotest.common.JSONArrayList;
import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.SimpleCallback;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.table.JSONObjectSet;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.RadioChooser;

import com.google.gwt.json.client.JSONArray;
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
        if (labelName.endsWith(PLATFORM_SUFFIX)) {
            int nameLength = labelName.length() - PLATFORM_SUFFIX.length();
            return labelName.substring(0, nameLength);
        }
        return labelName;
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

    public static String getJobTag(JSONObject job) {
        return Utils.jsonToString(job.get("id")) + "-" + Utils.jsonToString(job.get("owner"));
    }

    public static void populateRadioChooser(RadioChooser chooser, String name) {
        JSONArray options = staticData.getData(name + "_options").isArray();
        for (JSONString jsonOption : new JSONArrayList<JSONString>(options)) {
            chooser.addChoice(Utils.jsonToString(jsonOption));
        }
    }
}
