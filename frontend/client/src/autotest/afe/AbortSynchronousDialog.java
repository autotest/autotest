package autotest.afe;

import autotest.common.SimpleCallback;
import autotest.common.Utils;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.DialogBox;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.List;

class AbortSynchronousDialog extends DialogBox implements ClickListener {
    private SimpleCallback abortAsynchronousEntries;
    private JSONArray synchronousJobIds;
    private Button abortAll, abortAsynchronous, cancel;

    public AbortSynchronousDialog(SimpleCallback abortAsynchronousEntries, 
                                  Collection<JSONObject> synchronousJobs,
                                  boolean showAbortAsynchronous) {
        super(false, true);
        setText("Aborting synchronous jobs");
        this.abortAsynchronousEntries = abortAsynchronousEntries;
        String jobList = processJobs(synchronousJobs);

        String message = "The following jobs are synchronous. To abort part of the job, you must " +
                         "abort the entire job.";
        
        Panel contents = new VerticalPanel();
        contents.add(new Label(message));
        Label jobListLabel = new Label(jobList);
        jobListLabel.getElement().getStyle().setProperty("padding", "1em");
        contents.add(jobListLabel);
        
        abortAll = new Button("Abort full jobs");
        abortAll.addClickListener(this);
        abortAsynchronous = new Button("Abort asynchronous only");
        abortAsynchronous.addClickListener(this);
        cancel = new Button("Cancel");
        cancel.addClickListener(this);
        
        Panel buttons = new HorizontalPanel();
        buttons.add(abortAll);
        if (showAbortAsynchronous) {
            buttons.add(abortAsynchronous);
        }
        buttons.add(cancel);
        contents.add(buttons);
        
        add(contents);
    }
    
    /**
     * Compute a list of job IDs and a comma-separated list of job tags, returning the latter.
     */
    private String processJobs(Collection<JSONObject> synchronousJobs) {
        List<String> jobTags = new ArrayList<String>();
        synchronousJobIds = new JSONArray();
        for (JSONObject job : synchronousJobs) {
            jobTags.add(AfeUtils.getJobTag(job));
            synchronousJobIds.set(synchronousJobIds.size(), job.get("id"));
        }
        Collections.sort(jobTags);
        return Utils.joinStrings(", ", jobTags);
    }

    public void onClick(Widget sender) {
        if (sender == abortAll) {
            JSONObject params = new JSONObject();
            params.put("job__id__in", synchronousJobIds);
            AfeUtils.callAbort(params, abortAsynchronousEntries);
        } else if (sender == abortAsynchronous) {
            abortAsynchronousEntries.doCallback(this);
        }
        
        hide();
    }
}
