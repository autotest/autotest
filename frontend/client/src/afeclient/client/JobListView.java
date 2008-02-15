package afeclient.client;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONBoolean;
import com.google.gwt.json.client.JSONNull;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ChangeListener;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Hyperlink;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.Widget;

public class JobListView extends TabView {
    protected static final String ALL_USERS = "All Users";
    protected static final String SELECTED_LINK_STYLE = "selected-link";
    protected static final int JOBS_PER_PAGE = 30;
    protected static final String QUEUED_TOKEN = "queued", 
        RUNNING_TOKEN = "running", FINISHED_TOKEN = "finished", 
        ALL_TOKEN = "all";
    
    public String getElementId() {
        return "job_list";
    }

    protected JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    protected JSONObject jobFilterArgs = new JSONObject();
    protected JobTable.JobTableListener selectListener;

    protected JobTable jobTable;
    protected Hyperlink jobQueueLink, jobRunningLink, jobHistoryLink, 
                        allJobsLink, selectedLink = null;
    protected Button refreshButton;
    protected ListBox userList;
    protected Paginator paginator;

    protected Hyperlink nextLink, prevLink;

    protected void addCommonParams() {
        jobFilterArgs.put("query_limit", new JSONNumber(JOBS_PER_PAGE));
        jobFilterArgs.put("sort_by", new JSONString("-id"));
    }

    protected void addUserParam() {
        String user = userList.getValue(userList.getSelectedIndex());
        JSONValue value = JSONNull.getInstance();
        if (!user.equals(ALL_USERS))
            value = new JSONString(user);
        jobFilterArgs.put("owner", value);
    }
    
    protected void onFiltersChanged() {
        addUserParam();
        addCommonParams();
        resetPagination();
    }

    protected void selectQueued() {
        selectLink(jobQueueLink);
        jobFilterArgs = new JSONObject();
        jobFilterArgs.put("not_yet_run", JSONBoolean.getInstance(true));
        onFiltersChanged();
    }
    
    protected void selectRunning() {
        selectLink(jobRunningLink);
        jobFilterArgs = new JSONObject();
        jobFilterArgs.put("running", JSONBoolean.getInstance(true));
        onFiltersChanged();
    }

    protected void selectHistory() {
        selectLink(jobHistoryLink);
        jobFilterArgs = new JSONObject();
        jobFilterArgs.put("finished", JSONBoolean.getInstance(true));
        onFiltersChanged();
    }
    
    protected void selectAll() {
        selectLink(allJobsLink);
        jobFilterArgs = new JSONObject();
        onFiltersChanged();
    }

    protected void refresh() {
        updateNumJobs();
        jobTable.getJobs(jobFilterArgs);
    }

    protected void updateNumJobs() {
        rpcProxy.rpcCall("get_num_jobs", jobFilterArgs, new JsonRpcCallback() {
            public void onSuccess(JSONValue result) {
                int numJobs = (int) result.isNumber().getValue();
                paginator.setNumTotalResults(numJobs);
            }
        });
    }

    protected void populateUsers() {
        userList.addItem(ALL_USERS);
        
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONArray userArray = staticData.getData("users").isArray();
        String currentUser = staticData.getData("user_login").isString().stringValue();
        int numUsers = userArray.size();
        for (int i = 0; i < numUsers; i++) {
            String name = userArray.get(i).isString().stringValue();
            userList.addItem(name);
            if (name.equals(currentUser))
                userList.setSelectedIndex(i + 1); // +1 for "All users" at top
        }
    }

    protected void selectLink(Hyperlink link) {
        jobQueueLink.removeStyleName(SELECTED_LINK_STYLE);
        jobRunningLink.removeStyleName(SELECTED_LINK_STYLE);
        jobHistoryLink.removeStyleName(SELECTED_LINK_STYLE);
        allJobsLink.removeStyleName(SELECTED_LINK_STYLE);
        link.addStyleName(SELECTED_LINK_STYLE);
        selectedLink = link;
    }
    
    protected void resetPagination() {
        jobFilterArgs.put("query_start", new JSONNumber(0));
        paginator.setStart(0);
    }

    public JobListView(JobTable.JobTableListener listener) {
        selectListener = listener;
    }
    
    public void initialize() {
        jobTable = new JobTable(selectListener);
        jobTable.setClickable(true);
        RootPanel.get("job_table").add(jobTable);
        
        paginator = new Paginator(JOBS_PER_PAGE, new Paginator.PaginatorCallback() {
            public void doRequest(int start) {
                jobFilterArgs.put("query_start", new JSONNumber(start));
                refresh();
            }
        });
        RootPanel.get("job_pagination").add(paginator);
        
        ClickListener linkListener = new ClickListener() {
            public void onClick(Widget sender) {
                Hyperlink senderLink = (Hyperlink) sender;
                String fullToken = senderLink.getTargetHistoryToken();
                int prefixLength = JobListView.super.getHistoryToken().length();
                String linkToken = fullToken.substring(prefixLength + 1); // +1 for underscore
                handleHistoryToken(linkToken);
            }
        };

        jobQueueLink = new Hyperlink("Queued Jobs", 
                                     super.getHistoryToken() + "_" + QUEUED_TOKEN);
        jobQueueLink.addClickListener(linkListener);
        jobQueueLink.setStyleName("job-filter-link");
        
        jobRunningLink = new Hyperlink("Running Jobs",
                                       super.getHistoryToken() + "_" + RUNNING_TOKEN);
        jobRunningLink.addClickListener(linkListener);
        jobRunningLink.setStyleName("job-filter-link");

        jobHistoryLink = new Hyperlink("Finished Jobs",
                                       super.getHistoryToken() + "_" + FINISHED_TOKEN);
        jobHistoryLink.addClickListener(linkListener);
        jobHistoryLink.setStyleName("job-filter-link");
        
        allJobsLink = new Hyperlink("All Jobs",
                                    super.getHistoryToken() + "_" + ALL_TOKEN);
        allJobsLink.addClickListener(linkListener);
        allJobsLink.setStyleName("job-filter-link");

        HorizontalPanel jobLinks = new HorizontalPanel();
        RootPanel.get("job_control_links").add(jobLinks);
        jobLinks.add(jobQueueLink);
        jobLinks.add(jobRunningLink);
        jobLinks.add(jobHistoryLink);
        jobLinks.add(allJobsLink);
        
        refreshButton = new Button("Refresh");
        refreshButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                refresh();
            }
        });
        jobLinks.add(refreshButton);

        userList = new ListBox();
        userList.addChangeListener(new ChangeListener() {
            public void onChange(Widget sender) {
                addUserParam();
                resetPagination();
                refresh();
            }
        });
        populateUsers();
        RootPanel.get("user_list").add(userList);

        // all jobs is selected by default
        selectAll();
    }

    public String getHistoryToken() {
        return selectedLink.getTargetHistoryToken();
    }
    
    public void handleHistoryToken(String token) {
        if (token.equals(QUEUED_TOKEN)) {
            selectQueued();
        }
        else if (token.equals(RUNNING_TOKEN)) {
            selectRunning();
        }
        else if (token.equals(FINISHED_TOKEN)) {
            selectHistory();
        }
        else if (token.equals(ALL_TOKEN)) {
            selectAll();
        }
    }

    /**
     * Override to refresh the list every time the tab is displayed.
     */
    public void display() {
        super.display();
        refresh();
    }
}
