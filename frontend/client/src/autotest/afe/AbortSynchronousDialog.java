package autotest.afe;

import autotest.common.JSONArrayList;
import autotest.common.SimpleCallback;
import autotest.common.Utils;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.DialogBox;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.VerticalPanel;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

class AbortSynchronousDialog extends DialogBox implements ClickHandler {
    private SimpleCallback abortAsynchronousEntries;
    private JSONArray synchronousJobArgs;
    private Button abortAll, abortAsynchronous, cancel;

    public AbortSynchronousDialog(SimpleCallback abortAsynchronousEntries, 
                                  Collection<JSONObject> synchronousEntries,
                                  boolean showAbortAsynchronous) {
        super(false, true);
        setText("Aborting synchronous jobs");
        this.abortAsynchronousEntries = abortAsynchronousEntries;
        String jobList = processJobs(synchronousEntries);

        String message = "The following jobs are synchronous. To abort part of the job, you must " +
                         "abort the entire job.";
        
        Panel contents = new VerticalPanel();
        contents.add(new Label(message));
        Label jobListLabel = new Label(jobList);
        jobListLabel.getElement().getStyle().setProperty("padding", "1em");
        contents.add(jobListLabel);
        
        abortAll = new Button("Abort full jobs");
        abortAll.addClickHandler(this);
        abortAsynchronous = new Button("Abort asynchronous only");
        abortAsynchronous.addClickHandler(this);
        cancel = new Button("Cancel");
        cancel.addClickHandler(this);
        
        Panel buttons = new HorizontalPanel();
        buttons.add(abortAll);
        if (showAbortAsynchronous) {
            buttons.add(abortAsynchronous);
        }
        buttons.add(cancel);
        contents.add(buttons);
        
        add(contents);
    }
    
    private static String getGroupTag(JSONObject queueEntry) {
        JSONObject job = queueEntry.get("job").isObject();
        return AfeUtils.getJobTag(job) + "/" + Utils.jsonToString(queueEntry.get("execution_subdir"));
    }
    
    /**
     * Compute a list of job IDs and a comma-separated list of job tags, returning the latter.
     */
    private String processJobs(Collection<JSONObject> synchronousEntries) {
        Set<String> groupTags = new HashSet<String>();
        synchronousJobArgs = new JSONArray();
        for (JSONObject entry : synchronousEntries) {
            String groupTag = getGroupTag(entry);
            if (groupTags.contains(groupTag)) {
                continue;
            }
            groupTags.add(groupTag);
            JSONValue jobId = entry.get("job").isObject().get("id");
            JSONObject groupArgs = new JSONObject();
            groupArgs.put("job__id", jobId);
            groupArgs.put("execution_subdir", entry.get("execution_subdir"));
            synchronousJobArgs.set(synchronousJobArgs.size(), groupArgs);
        }
        List<String> groupTagList = new ArrayList<String>(groupTags);
        Collections.sort(groupTagList);
        return Utils.joinStrings(", ", groupTagList);
    }

    public void onClick(ClickEvent event) {
        if (event.getSource() == abortAll) {
            for (JSONObject groupParams : new JSONArrayList<JSONObject>(synchronousJobArgs)) {
                AfeUtils.callAbort(groupParams, null, false);
            }
            abortAsynchronousEntries.doCallback(this);
        } else if (event.getSource() == abortAsynchronous) {
            abortAsynchronousEntries.doCallback(this);
        }
        
        hide();
    }
}
